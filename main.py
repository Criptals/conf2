import os
import json
import zlib


def parse_object(object_hash, description=None):
    """
    Извлечь информацию из git-объекта по его хэшу.
    """
    # Полный путь к объекту по его хэшу
    object_path = os.path.join(config['repo_path'], '.git', 'objects', object_hash[:2], object_hash[2:])

    # Проверяем, существует ли файл с данным объектом
    if not os.path.exists(object_path):
        return None  # Возвращаем None, если объект не найден

    # Открываем git-объект
    with open(object_path, 'rb') as file:
        # Разжали объект, получили его сырое содержимое
        raw_object_content = zlib.decompress(file.read())
        # Разделили содержимое объекта на заголовок и основную часть
        header, raw_object_body = raw_object_content.split(b'\x00', maxsplit=1)
        # Извлекли из заголовка информацию о типе объекта и его размере
        object_type, content_size = header.decode().split(' ')

        # Словарь с данными git-объекта:
        object_dict = {}

        # В зависимости от типа объекта используем разные функции для его разбора
        if object_type == 'commit':
            object_dict['label'] = r'[commit]\n' + object_hash[:6]
            object_dict['children'] = parse_commit(raw_object_body)

        elif object_type == 'tree':
            object_dict['label'] = r'[tree]\n' + object_hash[:6]
            object_dict['children'] = parse_tree(raw_object_body)

        elif object_type == 'blob':
            object_dict['label'] = r'[blob]\n' + object_hash[:6]
            object_dict['children'] = []

        # Добавляем дополнительную информацию, если она была
        if description is not None:
            object_dict['label'] += r'\n' + description

        return object_dict


def parse_tree(raw_content):
    """
    Парсим git-объект дерева.
    """

    # Дети дерева (соответствующие строкам объекта)
    children = []

    # Парсим данные, последовательно извлекая информацию из каждой строки
    rest = raw_content
    while rest:
        # Извлечение режима
        mode, rest = rest.split(b' ', maxsplit=1)
        # Извлечение имени объекта
        name, rest = rest.split(b'\x00', maxsplit=1)
        # Извлечение хэша объекта и его преобразование в 16ричный формат
        sha1, rest = rest[:20].hex(), rest[20:]
        # Добавляем потомка к списку детей, если объект существует
        child = parse_object(sha1, description=name.decode())
        if child:  # Если объект существует, добавляем его в список детей
            children.append(child)

    return children


def parse_commit(raw_content):
    """
    Парсим git-объект коммита.
    """
    content = raw_content.decode()
    content_lines = content.split('\n')

    commit_data = {}

    # Извлекаем хэш объекта дерева
    commit_data['tree'] = content_lines[0].split()[1]
    content_lines = content_lines[1:]

    # Список родительских коммитов
    commit_data['parents'] = []
    while content_lines[0].startswith('parent'):
        commit_data['parents'].append(content_lines[0].split()[1])
        content_lines = content_lines[1:]

    while content_lines[0].strip():
        key, *values = content_lines[0].split()
        commit_data[key] = ' '.join(values)
        content_lines = content_lines[1:]

    commit_data['message'] = '\n'.join(content_lines[1:]).strip()

    # Возвращаем все зависимости объекта коммита (то есть его дерево и всех родителей)
    children = [parse_object(commit_data['tree'])]
    for parent in commit_data['parents']:
        parent_obj = parse_object(parent)
        if parent_obj:  # Проверяем, если родительский объект существует
            children.append(parent_obj)

    return children


def get_last_commit():
    """Получить хэш для последнего коммита в ветке"""
    head_path = os.path.join(config['repo_path'], '.git', 'refs', 'heads', config['branch'])
    with open(head_path, 'r') as file:
        return file.read().strip()


def generate_dot(filename):
    """Создать DOT-файл для графа зависимостей"""

    def recursive_write(file, tree):
        """Рекурсивно перебрать все узлы дерева для построения связей графа"""
        if tree and 'label' in tree:  # Проверяем наличие ключа 'label'
            label = tree['label']
            for child in tree['children']:
                if child and 'label' in child:  # Проверяем наличие ключа 'label' у потомка
                    file.write(f'    "{label}" -> "{child["label"]}"\n')
                    recursive_write(file, child)


    # Стартовая точка репозитория - последний коммит главной ветки
    last_commit = get_last_commit()
    # Строим дерево
    tree = parse_object(last_commit)
    # Описываем граф в DOT-нотации
    with open(filename, 'w') as file:
        file.write('digraph G {\n')
        if tree:
            recursive_write(file, tree)
        file.write('}')


# Достаем информацию из конфигурационного файла
with open('config.json', 'r') as f:
    config = json.load(f)

# Генерируем файл с DOT-нотацией графа зависимостей
generate_dot('graph.dot')
