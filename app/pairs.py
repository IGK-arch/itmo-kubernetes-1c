import csv
import io
import itertools
import re
from collections import Counter

# Predicate and skill normalization from lab 3, vacancy_lab/mapreduce.py.
PROGRAMMER = re.compile(r'программист|разработчик|developer|programmer', re.I)
ONE_C = re.compile(r'1[сc]', re.I)
BITRIX = re.compile(r'битрикс|bitrix', re.I)
JAVA_DEVELOPER = re.compile(r'java[\s-]+developer', re.I)


def belongs_to_variant(row):
    name = row.get('name', '')
    return bool(
        row.get('role') == 'Программист, разработчик'
        and ONE_C.search(name)
        and PROGRAMMER.search(name)
        and not BITRIX.search(name)
        and not JAVA_DEVELOPER.search(name)
    )


def count_pairs(rows):
    counts = Counter()
    total = selected = 0
    for row in rows:
        total += 1
        if belongs_to_variant(row):
            selected += 1
            skills = sorted({s.strip().lower() for s in row.get('key_skills', '').split(';') if s.strip()})
            counts.update(itertools.combinations(skills, 2))
    return counts, total, selected


def serialize(counts):
    data = io.StringIO(newline='')
    writer = csv.writer(data, lineterminator='\n')
    writer.writerow(('skill_1', 'skill_2', 'count'))
    writer.writerows((a, b, counts[a, b]) for a, b in sorted(counts))
    return data.getvalue().encode('utf-8')


def top_ten(counts):
    return [[a, b, n] for (a, b), n in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]]
