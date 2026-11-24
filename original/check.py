from collections import Counter
from job import event, memory, result
from vacancy_lab.mapreduce import run


if __name__=='__main__':
    event('start',mode='lab3-original')
    combined,meta=run('optimized')
    pairs=Counter({key[1:]:n for key,n in combined.items() if key[0]==2})
    _,summary=result(pairs,meta['rows_read'],meta['selected_vacancies'])
    event('result',**summary,**memory(),input_sha256=meta['input_sha256'],
          selected_ids_sha256=meta['selected_ids_sha256'],workers=meta['workers'])
