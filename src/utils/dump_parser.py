"""Парсер SQL-дампа для извлечения справочников"""

import re
from typing import Optional


def parse_insert_values(line: str) -> list[tuple]:
    """
    Извлечь значения из INSERT INTO ... VALUES (...), (...);

    Returns:
        Список кортежей значений
    """
    # Находим часть VALUES
    match = re.search(r'VALUES\s*(.+);?\s*$', line, re.IGNORECASE)
    if not match:
        return []

    values_part = match.group(1)
    results = []

    # Парсим каждый набор значений в скобках
    # Учитываем вложенные скобки и экранированные кавычки
    i = 0
    while i < len(values_part):
        if values_part[i] == '(':
            # Находим закрывающую скобку
            depth = 1
            start = i + 1
            i += 1
            in_string = False
            escape_next = False

            while i < len(values_part) and depth > 0:
                char = values_part[i]

                if escape_next:
                    escape_next = False
                elif char == '\\':
                    escape_next = True
                elif char == "'" and not escape_next:
                    in_string = not in_string
                elif not in_string:
                    if char == '(':
                        depth += 1
                    elif char == ')':
                        depth -= 1

                i += 1

            if depth == 0:
                value_str = values_part[start:i-1]
                values = parse_value_tuple(value_str)
                if values:
                    results.append(tuple(values))
        else:
            i += 1

    return results


def parse_value_tuple(value_str: str) -> list:
    """Распарсить строку значений внутри скобок"""
    values = []
    current = []
    in_string = False
    escape_next = False

    for char in value_str:
        if escape_next:
            current.append(char)
            escape_next = False
        elif char == '\\':
            escape_next = True
            current.append(char)
        elif char == "'" and not escape_next:
            in_string = not in_string
            current.append(char)
        elif char == ',' and not in_string:
            values.append(parse_single_value(''.join(current).strip()))
            current = []
        else:
            current.append(char)

    # Последнее значение
    if current:
        values.append(parse_single_value(''.join(current).strip()))

    return values


def parse_single_value(val: str) -> Optional[str]:
    """Распарсить одно значение"""
    if val.upper() == 'NULL':
        return None

    # Убираем кавычки
    if val.startswith("'") and val.endswith("'"):
        val = val[1:-1]
        # Разэкранируем
        val = val.replace("\\'", "'")
        val = val.replace("\\\\", "\\")
        val = val.replace("\\n", "\n")
        val = val.replace("\\r", "\r")
        val = val.replace("\\t", "\t")

    return val


def extract_categories(dump_path: str) -> dict[str, int]:
    """
    Извлечь категории из дампа

    Returns:
        Словарь {название: id}
    """
    categories = {}

    with open(dump_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'INSERT INTO `nulled_category_board`' in line:
                rows = parse_insert_values(line)
                for row in rows:
                    if len(row) >= 2:
                        try:
                            cat_id = int(row[0])
                            cat_name = row[1]
                            if cat_name:
                                categories[cat_name] = cat_id
                        except (ValueError, TypeError):
                            continue

    return categories


def extract_cities(dump_path: str) -> dict[str, dict]:
    """
    Извлечь города из дампа

    Returns:
        Словарь {название: {id, region_id, country_id}}
    """
    cities = {}

    with open(dump_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'INSERT INTO `nulled_city`' in line:
                rows = parse_insert_values(line)
                for row in rows:
                    if len(row) >= 4:
                        try:
                            city_id = int(row[0])
                            country_id = int(row[1]) if row[1] else 0
                            region_id = int(row[2]) if row[2] else 0
                            city_name = row[3]
                            if city_name:
                                cities[city_name] = {
                                    'id': city_id,
                                    'region_id': region_id,
                                    'country_id': country_id,
                                }
                        except (ValueError, TypeError):
                            continue

    return cities


def extract_regions(dump_path: str) -> dict[str, int]:
    """
    Извлечь регионы из дампа

    Returns:
        Словарь {название: id}
    """
    regions = {}

    with open(dump_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'INSERT INTO `nulled_region`' in line:
                rows = parse_insert_values(line)
                for row in rows:
                    if len(row) >= 3:
                        try:
                            region_id = int(row[0])
                            # region_name обычно в 3-м поле
                            region_name = row[2] if len(row) > 2 else row[1]
                            if region_name:
                                regions[region_name] = region_id
                        except (ValueError, TypeError):
                            continue

    return regions


def generate_mappings_code(dump_path: str) -> str:
    """
    Сгенерировать Python-код маппингов из дампа

    Args:
        dump_path: Путь к SQL-дампу

    Returns:
        Python-код с словарями маппингов
    """
    print("Извлечение категорий...")
    categories = extract_categories(dump_path)

    print("Извлечение городов...")
    cities = extract_cities(dump_path)

    print("Извлечение регионов...")
    regions = extract_regions(dump_path)

    lines = [
        '"""Автоматически сгенерированные маппинги из SQL-дампа"""',
        '',
        '# Маппинг категорий: название -> ID',
        'CATEGORY_IDS = {',
    ]

    for name, cat_id in sorted(categories.items(), key=lambda x: x[1]):
        lines.append(f'    "{name}": {cat_id},')
    lines.append('}')
    lines.append('')

    lines.append('# Маппинг городов: название -> ID')
    lines.append('CITY_IDS = {')
    for name, data in sorted(cities.items(), key=lambda x: x[1]['id']):
        lines.append(f'    "{name}": {data["id"]},')
    lines.append('}')
    lines.append('')

    lines.append('# Маппинг регионов: название -> ID')
    lines.append('REGION_IDS = {')
    for name, region_id in sorted(regions.items(), key=lambda x: x[1]):
        lines.append(f'    "{name}": {region_id},')
    lines.append('}')

    return '\n'.join(lines)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Использование: python dump_parser.py <путь_к_дампу.sql>")
        sys.exit(1)

    dump_path = sys.argv[1]
    print(f"Парсинг дампа: {dump_path}")

    code = generate_mappings_code(dump_path)

    output_path = "db_mappings.py"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(code)

    print(f"\nМаппинги сохранены в: {output_path}")
