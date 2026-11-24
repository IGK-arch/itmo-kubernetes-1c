import argparse
import csv
import hashlib
import io
import json
import os
import resource
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from pairs import count_pairs, serialize, top_ten

BUCKET = 'hh-lake'
KEY = 'raw/it_vacancies_2024.csv'
INPUT_SHA = '303db922b541e4440906f5a7e8be32fb55e8808f950ffddb8c272f1548212a65'
PREFIX = 'lab5/' + INPUT_SHA[:16]
CSV = '/input/it_vacancies_2024.csv'
csv.field_size_limit(16 * 1024 * 1024)


def event(name, **values):
    print(json.dumps(dict(event=name, utc=datetime.now(timezone.utc).isoformat(),
                          pod=os.environ.get('HOSTNAME'), **values), ensure_ascii=False), flush=True)


def memory():
    cg = Path('/sys/fs/cgroup')
    return dict(cgroup_peak_bytes=int((cg / 'memory.peak').read_text()),
                rss_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def s3_client():
    import boto3
    from botocore.config import Config
    return boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT'], region_name='us-east-1',
                        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'},
                                      request_checksum_calculation='when_required',
                                      response_checksum_validation='when_required'))


def put_json(s3, key, value):
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(value, ensure_ascii=False).encode())


def get_json(s3, key):
    with closing(s3.get_object(Bucket=BUCKET, Key=key)['Body']) as body:
        return json.loads(body.read())


def result(counts, rows, selected):
    data = serialize(counts)
    summary = dict(rows=rows, selected=selected, occurrences=sum(counts.values()), unique=len(counts),
                   sha256=hashlib.sha256(data).hexdigest(), top10=top_ten(counts))
    return data, summary


def single():
    with open(CSV, encoding='utf-8-sig', newline='') as stream:
        counts, rows, selected = count_pairs(csv.DictReader(stream))
    _, summary = result(counts, rows, selected)
    event('result', **summary, **memory())


class LinesWithOffsets:
    """Binary positions after physical lines consumed by csv.reader, including quoted newlines."""
    def __init__(self, stream):
        self.stream = stream
        self.offset = 0
        self.sha = hashlib.sha256()

    def __iter__(self):
        return self

    def __next__(self):
        line = self.stream.readline()
        if not line:
            raise StopIteration
        codec = 'utf-8' if self.offset else 'utf-8-sig'
        self.offset += len(line)
        self.sha.update(line)
        return line.decode(codec)


def index_file(s3, parts):
    obj = s3.get_object(Bucket=BUCKET, Key=KEY)
    size = obj['ContentLength']
    ranges = []
    with io.BufferedReader(obj['Body'], buffer_size=1024 * 1024) as stream:
        lines = LinesWithOffsets(stream)
        reader = csv.reader(lines)
        fields = next(reader)
        start = lines.offset
        rows = 0
        for record in reader:
            if len(record) != len(fields):
                raise ValueError(f'Unexpected column count at byte {lines.offset}')
            rows += 1
            if len(ranges) < parts - 1 and lines.offset >= size * (len(ranges) + 1) // parts:
                ranges.append(dict(start=start, end=lines.offset - 1, rows=rows))
                start, rows = lines.offset, 0
        ranges.append(dict(start=start, end=lines.offset - 1, rows=rows))
    assert lines.sha.hexdigest() == INPUT_SHA and lines.offset == size and len(ranges) == parts
    assert all(r['rows'] > 0 for r in ranges)
    manifest = dict(key=KEY, etag=obj['ETag'], sha256=INPUT_SHA, bytes=size, fields=fields, ranges=ranges)
    put_json(s3, PREFIX + '/index.json', manifest)
    event('index', **{k: v for k, v in manifest.items() if k != 'fields'})


def map_range(s3):
    index = int(os.environ['JOB_COMPLETION_INDEX'])
    manifest = get_json(s3, PREFIX + '/index.json')
    part = manifest['ranges'][index]
    byte_range = f"bytes={part['start']}-{part['end']}"
    obj = s3.get_object(Bucket=BUCKET, Key=KEY, Range=byte_range, IfMatch=manifest['etag'])
    assert obj['ResponseMetadata']['HTTPStatusCode'] == 206
    assert obj['ContentRange'] == f"bytes {part['start']}-{part['end']}/{manifest['bytes']}"
    event('range', index=index, requested=byte_range, http=206, bytes=obj['ContentLength'])
    with io.TextIOWrapper(io.BufferedReader(obj['Body'], buffer_size=1024 * 1024), encoding='utf-8', newline='') as stream:
        counts, rows, selected = count_pairs(csv.DictReader(stream, fieldnames=manifest['fields']))
    assert rows == part['rows']
    key = PREFIX + f'/part-{index}'
    data = serialize(counts)
    sha = hashlib.sha256(data).hexdigest()
    s3.put_object(Bucket=BUCKET, Key=key + '.csv', Body=data)
    info = dict(index=index, rows=rows, selected=selected, occurrences=sum(counts.values()),
                unique=len(counts), sha256=sha, etag=manifest['etag'])
    put_json(s3, key + '.json', info)
    event('partial', **info, **memory())


def reduce_parts(s3):
    manifest = get_json(s3, PREFIX + '/index.json')
    counts = Counter()
    rows = selected = emitted = 0
    for index, part in enumerate(manifest['ranges']):
        key = PREFIX + f'/part-{index}'
        meta = get_json(s3, key + '.json')
        with closing(s3.get_object(Bucket=BUCKET, Key=key + '.csv')['Body']) as body:
            raw = body.read()
        assert meta['index'] == index and meta['rows'] == part['rows'] and meta['etag'] == manifest['etag']
        assert hashlib.sha256(raw).hexdigest() == meta['sha256']
        for row in csv.DictReader(io.StringIO(raw.decode(), newline='')):
            counts[row['skill_1'], row['skill_2']] += int(row['count'])
        rows += meta['rows']
        selected += meta['selected']
        emitted += meta['occurrences']
    data, summary = result(counts, rows, selected)
    assert emitted == summary['occurrences']
    s3.put_object(Bucket=BUCKET, Key=PREFIX + '/skills_2.csv', Body=data)
    put_json(s3, PREFIX + '/summary.json', summary)
    event('result', **summary, **memory())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['single', 'index', 'map', 'reduce'])
    parser.add_argument('--parts', type=int, default=4)
    args = parser.parse_args()
    event('start', mode=args.command)
    if args.command == 'single':
        single()
    else:
        client = s3_client()
        if args.command == 'index':
            index_file(client, args.parts)
        elif args.command == 'map':
            map_range(client)
        else:
            reduce_parts(client)
