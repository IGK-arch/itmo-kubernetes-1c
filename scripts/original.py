import json
import math
from kube import ROOT, E, new_job, run_job, write_json


if __name__=='__main__':
    old=json.loads((ROOT/'reference/lab3-memory.json').read_text())['optimized']['maximum_peak_rss_mib']
    limit=16*math.ceil(old*1.25/16)
    job=new_job('pairs-lab3-original','original',f'{limit}Mi','192Mi',cpu='2',request_cpu='500m')
    container=job['spec']['template']['spec']['containers'][0]
    container['image']='skills-1c:original'
    container['args']=[]
    container['env']=[
        dict(name='RUSTFS_ENDPOINT_URL',value='http://rustfs.skills-1c.svc.cluster.local:9000'),
        dict(name='RUSTFS_ACCESS_KEY',valueFrom=dict(secretKeyRef=dict(name='s3-auth',key='AWS_ACCESS_KEY_ID'))),
        dict(name='RUSTFS_SECRET_KEY',valueFrom=dict(secretKeyRef=dict(name='s3-auth',key='AWS_SECRET_ACCESS_KEY')))]
    run_job('pairs-lab3-original',job)
    record=json.loads((E/'pairs-lab3-original.log').read_text().splitlines()[-1])
    reference=json.loads((ROOT/'results/verification.json').read_text())
    assert record['sha256']==reference['sha256']
    assert record['top10']==[[t['skill_1'],t['skill_2'],t['lab3']] for t in reference['top10']]
    write_json(E/'original-comparison.json',dict(old_rss_max_mib=old,limit_mib=limit,result=record))
