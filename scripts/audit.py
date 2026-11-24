"""Cross-check the recorded run using only the Python standard library."""
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'evidence'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def run():
    expected='395e69c74e4515b36b765932f41aef0c5767d04ce67cc7646068a535bbc47b15'
    baseline=(ROOT/'reference/skills_2.csv').read_bytes()
    result=(ROOT/'results/skills_2.csv').read_bytes()
    assert hashlib.sha256(result).hexdigest()==expected and baseline==result
    previous=ROOT.parent/'lab3-mapreduce'
    if previous.exists():
        assert result==(previous/'results/optimized-1/skills_2.csv').read_bytes()
        for f in (ROOT/'original/src/vacancy_lab').glob('*.py'):
            assert f.read_bytes()==(previous/'src/vacancy_lab'/f.name).read_bytes()
    with (ROOT/'reference/skills_2.csv').open(encoding='utf-8',newline='') as f:
        all_pairs=sorted([(r['skill_1'],r['skill_2'],int(r['count'])) for r in csv.DictReader(f)],
                         key=lambda t:(-t[2],t[:2]))
    with (ROOT/'results/top10.csv').open(encoding='utf-8',newline='') as f:
        ten=list(csv.DictReader(f))
    assert len(ten)==10
    for i,(row,(a,b,count)) in enumerate(zip(ten,all_pairs),1):
        assert (row['skill_1'],row['skill_2'],int(row['rank']))==(a,b,i)
        assert int(row['kubernetes'])==int(row['lab3'])==count
    for name in ('pairs-profile','pairs-tuned','pairs-reduce','pairs-lab3-original'):
        line=json.loads((E/(name+'.log')).read_text(encoding='utf-8').splitlines()[-1])
        assert line['sha256']==expected and line['top10']==[list(r) for r in all_pairs[:10]]
        assert (line['rows'],line['selected'],line['unique'],line['occurrences'])==(229388,18164,28430,214983)
        assert read(E/(name+'-job.json'))['status']['succeeded']==1
    m=read(E/'memory.json')
    term=read(E/'pairs-oom-pods.json')[0]['status']['containerStatuses'][0]['state']['terminated']
    assert (term['reason'],term['exitCode'])==('OOMKilled',137)
    assert m['limit_mib']==16*math.ceil(m['profile']['cgroup_peak_bytes']*1.25/(16*2**20))
    tuned=read(ROOT/'manifests/pairs-tuned.json')['spec']['template']['spec']['containers'][0]
    assert tuned['resources']['limits']['memory']==f"{m['limit_mib']}Mi"
    old=read(E/'original-comparison.json')
    assert old['limit_mib']==16*math.ceil(old['old_rss_max_mib']*1.25/16)
    ref={r['key']:r['sha256'] for r in read(ROOT/'reference/lab2-objects.json')}
    raw_sha='303db922b541e4440906f5a7e8be32fb55e8808f950ffddb8c272f1548212a65'
    ref['raw/it_vacancies_2024.csv']=raw_sha
    migrated=read(E/'migration.json')
    assert len(migrated)==4 and {x['key']:x['sha256'] for x in migrated}==ref
    assert all(x['source_http']==x['target_http']==200 for x in migrated)
    claims=read(E/'persistent-volumes.json')
    assert len({c['volume'] for c in claims})==4 and all(c['phase']=='Bound' for c in claims)
    index=json.loads((E/'pairs-index.log').read_text().splitlines()[-1])
    assert index['sha256']==raw_sha and index['ranges'][-1]['end']==index['bytes']-1
    assert all(a['end']+1==b['start'] for a,b in zip(index['ranges'],index['ranges'][1:]))
    maps=read(E/'map-overlap.json')
    assert len({s['pod'] for s in maps})==4 and [s['index'] for s in maps]==[0,1,2,3]
    for part,s in zip(index['ranges'],maps):
        assert s['range']['http']==206 and s['range']['bytes']==part['end']-part['start']+1
        assert s['result']['rows']==part['rows']
    assert sum(s['result']['rows'] for s in maps)==229388 and sum(s['result']['selected'] for s in maps)==18164
    assert max(datetime.fromisoformat(s['start']) for s in maps)<min(datetime.fromisoformat(s['end']) for s in maps)
    sched=read(E/'scheduling.json')
    events=read(E/'events-skills-1c.json')
    def by_name(name):
        return [e for e in events if e['involvedObject']['kind']=='Pod' and e['involvedObject']['name']==name]
    waiting=by_name(sched['waiter'])
    assert len({e['involvedObject']['uid'] for e in waiting})==1
    assert any(e['reason']=='FailedScheduling' and 'Insufficient cpu' in e['message'] for e in waiting)
    assert any(e['reason']=='Started' for e in waiting)
    high_uid=next(e['involvedObject']['uid'] for e in by_name(sched['high']) if e['reason']=='Started')
    assert any(e['reason']=='Preempted' and high_uid in e['message'] for e in by_name(sched['low']))
    quota=read(E/'quota-result.json')
    assert quota['used_m']+quota['request_m']>quota['hard_m'] and quota['after_release']=='Running'
    assert all(x in quota['rejected'] for x in ('Forbidden','exceeded quota','500m','750m'))
    screenshots=list((E/'screenshots').glob('*.png'))
    assert len({hashlib.sha256(p.read_bytes()).hexdigest() for p in screenshots})==len(screenshots)==4
    print('Verified OOM and memory sizing, four PVCs and migrated objects, four simultaneous ranges,')
    print('full CSV and top 10, original lab 3 code, scheduler victim UID, wait events and quota.')


if __name__=='__main__':
    run()
