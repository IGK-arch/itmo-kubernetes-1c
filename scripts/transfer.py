"""Copy the two courses' input objects through the S3 API; verify downloaded bytes."""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if sys.platform == 'win32':
    sys.path.insert(0, str(ROOT.parent/'lab4-zookeeper/python-packages'))
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError

PREFIX = 'lab5/303db922b541e444'
RAW = 'raw/it_vacancies_2024.csv'
SHA = '303db922b541e4440906f5a7e8be32fb55e8808f950ffddb8c272f1548212a65'


def client(endpoint, access, secret):
    return boto3.client('s3', endpoint_url=endpoint, aws_access_key_id=access,
                        aws_secret_access_key=secret, region_name='us-east-1',
                        config=Config(signature_version='s3v4', s3={'addressing_style':'path'},
                                      request_checksum_calculation='when_required',
                                      response_checksum_validation='when_required',
                                      connect_timeout=10, read_timeout=100))


def target():
    keys=json.loads((ROOT/'tmp/s3-auth.json').read_text())
    return client(os.environ.get('CLUSTER_ENDPOINT','http://127.0.0.1:19021'),
                  keys['AWS_ACCESS_KEY_ID'],keys['AWS_SECRET_ACCESS_KEY'])


def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def migrate():
    access,secret=os.getenv('LEGACY_ACCESS_KEY'),os.getenv('LEGACY_SECRET_KEY')
    if not access and not secret:
        keys=json.loads((ROOT.parent/'lab/.credentials.json').read_text())
        access,secret=keys['access'],keys['secret']
    if not (access and secret):
        raise ValueError('Set both LEGACY_ACCESS_KEY and LEGACY_SECRET_KEY.')
    src=client(os.environ.get('LEGACY_ENDPOINT','http://127.0.0.1:19020'),access,secret)
    dst=target()
    original=json.loads((ROOT/'reference/lab2-objects.json').read_text())
    objects=[('it-vacancies',o['key'],o['sha256']) for o in original]+[('hh-lake',RAW,SHA)]
    checks=[]
    for bucket in sorted({b for b,_,_ in objects}):
        try:
            dst.head_bucket(Bucket=bucket)
        except ClientError as exc:
            if exc.response['ResponseMetadata']['HTTPStatusCode']!=404:
                raise
            dst.create_bucket(Bucket=bucket)
    for bucket,key,expected in objects:
        obj=src.get_object(Bucket=bucket,Key=key)
        with closing(obj['Body']) as source:
            dst.upload_fileobj(source,bucket,key,Config=TransferConfig(multipart_threshold=8*2**20,
                               multipart_chunksize=8*2**20,use_threads=False))
        copy=dst.get_object(Bucket=bucket,Key=key)
        with closing(copy['Body']) as body:
            digest=hashlib.sha256()
            for chunk in body.iter_chunks(chunk_size=2**20):
                digest.update(chunk)
        assert digest.hexdigest()==expected and obj['ContentLength']==copy['ContentLength']
        checks.append(dict(bucket=bucket,key=key,bytes=copy['ContentLength'],sha256=digest.hexdigest(),
                           source_http=obj['ResponseMetadata']['HTTPStatusCode'],
                           target_http=copy['ResponseMetadata']['HTTPStatusCode']))
        print(f"GET / PUT / GET  s3://{bucket}/{key}  {copy['ContentLength']} bytes  SHA-256 OK",flush=True)
        save(ROOT/'evidence/migration.json',checks)


def verify():
    dst=target()
    def fetch(key):
        with closing(dst.get_object(Bucket='hh-lake',Key=PREFIX+'/'+key)['Body']) as body:
            return body.read()
    computed=fetch('skills_2.csv')
    (ROOT/'results/skills_2.csv').write_bytes(computed)
    reference=(ROOT/'reference/skills_2.csv').read_bytes()
    previous=ROOT.parent/'lab3-mapreduce/results/optimized-1/skills_2.csv'
    if previous.exists():
        assert previous.read_bytes()==reference
    def rank(raw):
        rows=list(csv.DictReader(io.StringIO(raw.decode(),newline='')))
        return sorted([(x['skill_1'],x['skill_2'],int(x['count'])) for x in rows],
                      key=lambda r:(-r[2],r[:2]))
    a,b=rank(reference),rank(computed)
    summary=json.loads(fetch('summary.json'))
    evidence=json.loads((ROOT/'evidence/memory.json').read_text(encoding='utf-8'))
    sha=hashlib.sha256(computed).hexdigest()
    assert a==b and computed==reference and summary['sha256']==sha
    assert evidence['tuned']['sha256']==sha and evidence['profile']['sha256']==sha
    assert list(map(list,b[:10]))==summary['top10']==evidence['tuned']['top10']
    assert sum(x[2] for x in b)==summary['occurrences'] and len(b)==summary['unique']
    table=[dict(rank=i,skill_1=p[0],skill_2=p[1],lab3=p[2],kubernetes=q[2])
           for i,(p,q) in enumerate(zip(a[:10],b[:10]),1)]
    save(ROOT/'results/verification.json',dict(bytes=len(computed),sha256=sha,full_csv_equal=True,
         rows=summary['rows'],selected=summary['selected'],occurrences=summary['occurrences'],
         unique=len(b),top10=table))
    with (ROOT/'results/top10.csv').open('w',encoding='utf-8',newline='') as out:
        w=csv.DictWriter(out,fieldnames=list(table[0]),lineterminator='\n')
        w.writeheader()
        w.writerows(table)
    for row in table:
        print(row['rank'],row['skill_1'],row['skill_2'],row['lab3'],row['kubernetes'],sep=' | ')
    print('Full CSV is identical:',len(b),'pairs;',len(computed),'bytes;',sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['migrate','verify'])
    args=parser.parse_args()
    (migrate if args.action=='migrate' else verify)()
