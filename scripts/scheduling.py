import re
from kube import E, M, NS, IMAGE, call, get, manifest, wait_for, write_json


def milli(value):
    return int(value[:-1]) if value.endswith('m') else int(value)*1000


def sleeper(name, cpu, priority=None, ns=NS, as_job=True):
    pod=dict(restartPolicy='Never', terminationGracePeriodSeconds=2, automountServiceAccountToken=False,
             containers=[dict(name='hold',image=IMAGE,imagePullPolicy='Never',
                              command=['python','-c','import time; time.sleep(1800)'],
                              resources=dict(requests=dict(cpu=f'{cpu}m',memory='16Mi'),
                                             limits=dict(cpu=f'{cpu}m',memory='64Mi')))])
    if priority:
        pod['priorityClassName']=priority
    meta=dict(name=name,namespace=ns)
    if as_job:
        return dict(apiVersion='batch/v1',kind='Job',metadata=meta,spec=dict(backoffLimit=2,template=dict(spec=pod)))
    return dict(apiVersion='v1',kind='Pod',metadata=meta,spec=pod)


def launch(name,cpu,priority=None,ns=NS,as_job=True,check=True):
    path=manifest(name,sleeper(name,cpu,priority,ns,as_job))
    return call('create','-f',path,ns=ns,check=check,evidence=name+'-create.txt')


def job_pod(name,phase):
    def match():
        return next((p for p in get('pods','-l','job-name='+name)['items']
                     if p['status']['phase']==phase and 'deletionTimestamp' not in p['metadata']),None)
    return wait_for(match)


def events(uid,reason=None):
    obj=get('events','--field-selector','involvedObject.uid='+uid)['items']
    return [e for e in obj if not reason or reason.lower() in (e['reason']+' '+e['message']).lower()]


def scheduling():
    node=get('nodes',ns=None)['items'][0]
    alloc=milli(node['status']['allocatable']['cpu'])
    desc=call('describe','node',node['metadata']['name'],ns=None,evidence='node-before-cpu.txt').stdout
    line=re.search(r'^\s*cpu\s+(\S+)\s+\(',desc.split('Allocated resources:')[-1],re.M)
    used=milli(line.group(1))
    free=alloc-used
    hold=free-500
    ask=1000
    assert hold>=ask
    launch('cpu-holder',hold)
    holder=job_pod('cpu-holder','Running')
    launch('cpu-wait',ask)
    waiter=job_pod('cpu-wait','Pending')
    failures=wait_for(lambda: events(waiter['metadata']['uid'],'Insufficient cpu'))
    call('describe','pod',waiter['metadata']['name'],evidence='cpu-wait-pending.txt')
    call('get','pods','-l','job-name in (cpu-holder,cpu-wait)','-o','wide',evidence='cpu-simultaneous.txt')
    call('delete','job','cpu-holder','--cascade=foreground','--wait=true')
    released=job_pod('cpu-wait','Running')
    assert waiter['metadata']['uid']==released['metadata']['uid']
    call('get','pod',released['metadata']['name'],'-o','wide',evidence='cpu-after-release.txt')
    call('delete','job','cpu-wait','--cascade=foreground','--wait=true')
    call('apply','-f',M/'priorities.yaml',ns=None)
    launch('priority-low',hold,'j3312-low')
    low=job_pod('priority-low','Running')
    uid=low['metadata']['uid']
    call('get','pod',low['metadata']['name'],'-o','wide',evidence='low-before.txt')
    launch('priority-high',ask,'j3312-high')
    high=job_pod('priority-high','Running')
    eviction=wait_for(lambda: events(uid,'preempt'))
    call('get','events','--field-selector','involvedObject.uid='+uid,evidence='low-preempted.txt')
    call('get','pods','-l','job-name in (priority-low,priority-high)','-o','wide',evidence='priority-after.txt')
    call('describe','pod',high['metadata']['name'],evidence='high-running.txt')
    call('delete','job','priority-high','--cascade=foreground','--wait=true')
    replacement=job_pod('priority-low','Running')
    assert replacement['metadata']['uid']!=uid
    call('get','pod',replacement['metadata']['name'],'-o','wide',evidence='low-replacement.txt')
    call('delete','job','priority-low','--cascade=foreground','--wait=true')
    write_json(E/'scheduling.json',dict(allocatable_m=alloc,initial_requests_m=used,free_m=free,
        holder_request_m=hold,waiting_request_m=ask,holder=holder['metadata']['name'],
        waiter=waiter['metadata']['name'],same_waiter_after_release=True,
        failed_scheduling=[e['message'] for e in failures],low=low['metadata']['name'],
        high=high['metadata']['name'],low_replacement=replacement['metadata']['name'],
        eviction=[dict(reason=e['reason'],message=e['message']) for e in eviction],
        low_priority=low['spec']['priority'],high_priority=high['spec']['priority']))


def quota():
    ns='skills-quota'
    call('apply','-f',M/'quota.yaml',ns=None)
    wait_for(lambda: get('quota','cpu-budget',ns=ns).get('status',{}).get('hard'))
    launch('quota-first',750,ns=ns,as_job=False)
    wait_for(lambda: get('pod','quota-first',ns=ns)['status']['phase']=='Running')
    wait_for(lambda: get('quota','cpu-budget',ns=ns)['status']['used']['requests.cpu']=='750m')
    call('describe','quota','cpu-budget',ns=ns,evidence='quota-used.txt')
    denied=launch('quota-second',500,ns=ns,as_job=False,check=False)
    assert denied.returncode and 'exceeded quota' in denied.stderr and 'Forbidden' in denied.stderr
    assert call('get','pod','quota-second',ns=ns,check=False).returncode!=0
    call('get','pods',ns=ns,evidence='quota-denied-pods.txt')
    call('delete','pod','quota-first',ns=ns)
    wait_for(lambda: milli(get('quota','cpu-budget',ns=ns)['status']['used']['requests.cpu'])==0)
    call('create','-f',M/'quota-second.json',ns=ns,evidence='quota-after-release.txt')
    wait_for(lambda: get('pod','quota-second',ns=ns)['status']['phase']=='Running')
    call('get','pods',ns=ns,evidence='quota-second-running.txt')
    call('describe','quota','cpu-budget',ns=ns,evidence='quota-final.txt')
    write_json(E/'quota-result.json',dict(namespace=ns,hard_m=1000,used_m=750,request_m=500,
               rejected=denied.stderr.strip(),after_release='Running'))
    call('delete','pod','quota-second',ns=ns)


if __name__=='__main__':
    scheduling()
    quota()
    print('CPU wait, preemption and namespace quota confirmed.',flush=True)
