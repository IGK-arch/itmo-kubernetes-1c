import argparse
import json
import math
import secrets
from kube import E, M, ROOT, call, get, new_job, run_job, write_json


def memory_runs():
    call('apply', '-f', M/'namespace.yaml')
    pods = run_job('pairs-oom', new_job('pairs-oom', 'single', '12Mi', '8Mi'), expect_failure=True)
    state = pods[0]['status']['containerStatuses'][0]['state']['terminated']
    if (state['reason'], state['exitCode']) != ('OOMKilled', 137):
        raise RuntimeError(state)
    run_job('pairs-profile', new_job('pairs-profile', 'single', '768Mi', '64Mi'))
    def result(name):
        return next(d for d in map(json.loads, (E/(name+'.log')).read_text().splitlines()) if d['event']=='result')
    profile = result('pairs-profile')
    peak = profile['cgroup_peak_bytes']
    limit_mib = 16 * math.ceil(peak * 1.25 / (16 * 2 ** 20))
    request_mib = min(limit_mib, max(16, 16 * math.ceil(profile['rss_peak_kib'] / (16 * 1024))))
    run_job('pairs-tuned', new_job('pairs-tuned', 'single', f'{limit_mib}Mi', f'{request_mib}Mi'))
    tuned = result('pairs-tuned')
    assert profile['sha256'] == tuned['sha256'] and tuned['cgroup_peak_bytes'] <= limit_mib * 2**20
    write_json(E/'memory.json', dict(oom=state, profile=profile, margin=1.25, rounding_mib=16,
                                     limit_mib=limit_mib, request_mib=request_mib, tuned=tuned))
    print(f"OOMKilled {state['exitCode']}; profile {peak} bytes; limit {limit_mib}Mi; tuned complete", flush=True)


def storage():
    call('apply', '-f', M/'namespace.yaml')
    auth = ROOT/'tmp/s3-auth.json'
    if not auth.exists():
        write_json(auth, dict(AWS_ACCESS_KEY_ID='lab5-'+secrets.token_hex(6),
                              AWS_SECRET_ACCESS_KEY=secrets.token_urlsafe(32)))
    secret = dict(apiVersion='v1',kind='Secret',metadata=dict(name='s3-auth', namespace='skills-1c'),
                  stringData=json.loads(auth.read_text()))
    call('apply', '-f', '-', stdin=json.dumps(secret))
    call('apply', '-f', M/'rustfs.yaml')
    call('rollout', 'status', 'statefulset/rustfs', '--timeout=240s')
    call('get','sts,pod,svc,pvc','-o','wide',evidence='storage-resources.txt')
    call('logs','rustfs-0','--tail=100',evidence='rustfs.log')
    assert len([v for v in get('pvc')['items'] if v['status']['phase']=='Bound'])==4


def parallel():
    run_job('pairs-index', new_job('pairs-index','index','256Mi','64Mi'))
    pods = run_job('pairs-map', new_job('pairs-map','map','384Mi','96Mi',cpu='1',request_cpu='500m'))
    run_job('pairs-reduce', new_job('pairs-reduce','reduce','256Mi','64Mi'))
    spans = []
    for pod in pods:
        idx = int(pod['metadata']['annotations']['batch.kubernetes.io/job-completion-index'])
        events = [json.loads(s) for s in (E/f'pairs-map-{idx}.log').read_text().splitlines()]
        spans.append(dict(index=idx, pod=pod['metadata']['name'], start=events[0]['utc'],
                          end=events[-1]['utc'], range=events[1], result=events[-1]))
    spans.sort(key=lambda p:p['index'])
    assert [p['index'] for p in spans]==list(range(4))
    assert max(p['start'] for p in spans) < min(p['end'] for p in spans)
    write_json(E/'map-overlap.json',spans)
    print('Four distinct indexes; all four processing intervals overlap.',flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['memory','storage','parallel'])
    args=p.parse_args()
    {'memory':memory_runs,'storage':storage,'parallel':parallel}[args.stage]()
