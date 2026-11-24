from kube import E, get, write_json


if __name__ == '__main__':
    for namespace in ('skills-1c','skills-quota'):
        write_json(E/f'events-{namespace}.json',get('events',ns=namespace)['items'])
    claims=get('pvc')['items']
    write_json(E/'persistent-volumes.json',[
        dict(claim=c['metadata']['name'],volume=c['spec']['volumeName'],phase=c['status']['phase'],
             capacity=c['status']['capacity']['storage'],storage_class=c['spec']['storageClassName'])
        for c in claims])
