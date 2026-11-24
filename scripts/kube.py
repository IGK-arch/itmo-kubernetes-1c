"""kubectl access scoped to the lab's kubeconfig and namespace."""
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'evidence'
M = ROOT / 'manifests'
NS = 'skills-1c'
IMAGE = 'skills-1c:lab5'
os.environ.setdefault('KUBECONFIG', '/var/lib/itmo-j3312-k8s/kubeconfig')
os.environ['PATH'] = '/opt/itmo-j3312-k8s/bin:' + os.environ['PATH']


def call(*args, ns=NS, evidence=None, check=True, stdin=None):
    parts = [str(a.relative_to(ROOT)) if isinstance(a, Path) and a.is_relative_to(ROOT) else str(a)
             for a in args]
    cmd = ['kubectl', *(('-n', ns) if ns else ()), *parts]
    p = subprocess.run(cmd, cwd=ROOT, text=True, encoding='utf-8', input=stdin, capture_output=True)
    if evidence:
        text = '$ ' + shlex.join(cmd) + '\n' + p.stdout + p.stderr
        (E / evidence).write_text(text, encoding='utf-8')
    if check and p.returncode:
        raise RuntimeError(f'{shlex.join(cmd)}\n{p.stderr}')
    return p


def get(*args, ns=NS):
    return json.loads(call('get', *args, '-o', 'json', ns=ns).stdout)


def wait_for(fn, timeout=240):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(1)
    raise TimeoutError(fn.__name__)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def manifest(name, obj):
    path = M / (name + '.json')
    write_json(path, obj)
    return path


def new_job(name, mode, memory_limit, memory_request, cpu='1', request_cpu='250m'):
    app = dict(name='pairs', image=IMAGE, imagePullPolicy='Never', args=[mode],
               resources=dict(requests=dict(cpu=request_cpu, memory=memory_request),
                              limits=dict(cpu=cpu, memory=memory_limit)))
    spec = dict(restartPolicy='Never', containers=[app], automountServiceAccountToken=False)
    if mode == 'single':
        app['volumeMounts'] = [dict(name='csv', mountPath='/input/it_vacancies_2024.csv', readOnly=True)]
        spec['volumes'] = [dict(name='csv', hostPath=dict(path='/lab-input/it_vacancies_2024.csv', type='File'))]
    else:
        app['env'] = [dict(name='S3_ENDPOINT', value='http://rustfs.skills-1c.svc.cluster.local:9000')]
        app['envFrom'] = [dict(secretRef=dict(name='s3-auth'))]
    job = dict(apiVersion='batch/v1', kind='Job', metadata=dict(name=name, namespace=NS),
               spec=dict(backoffLimit=0, template=dict(spec=spec)))
    if mode == 'map':
        job['spec'].update(completionMode='Indexed', completions=4, parallelism=4)
    return job


def run_job(name, spec, expect_failure=False):
    path = manifest(name, spec)
    call('create', '-f', path)
    def closed():
        return any(c.get('status') == 'True' and c['type'] in ('Complete', 'Failed')
                   for c in get('job', name)['status'].get('conditions', []))
    wait_for(closed, timeout=900)
    job = get('job', name)
    pods = get('pods', '-l', 'job-name=' + name)['items']
    write_json(E / (name + '-job.json'), job)
    write_json(E / (name + '-pods.json'), pods)
    call('get', 'pods', '-l', 'job-name='+name, '-o', 'wide', evidence=name+'-get.txt')
    for pod in pods:
        pod_name = pod['metadata']['name']
        suffix = pod['metadata'].get('annotations', {}).get('batch.kubernetes.io/job-completion-index', '')
        log_file = name + ('-' + suffix if suffix else '') + '.log'
        raw = call('logs', pod_name, check=False)
        (E / log_file).write_text(raw.stdout + raw.stderr, encoding='utf-8')
        call('describe', 'pod', pod_name, evidence=log_file[:-4] + '-describe.txt')
    failed = bool(job['status'].get('failed'))
    if failed != expect_failure:
        raise RuntimeError(f'{name}: unexpected status {job["status"]}')
    return pods
