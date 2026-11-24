import json
import os
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
if (ROOT.parent/'lab4-zookeeper/python-packages').exists():
    sys.path.insert(0,str(ROOT.parent/'lab4-zookeeper/python-packages'))
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))


def n(value):
    return f'{value:,}'.replace(',','\u00a0')


def dec(value, places=1):
    return f'{value:.{places}f}'.replace('.',',')


def duration(a,b):
    return (datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()


class Report:
    def __init__(self, path):
        fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        for name,file in [('Body','times.ttf'),('Bold','timesbd.ttf'),('Italic','timesi.ttf'),
                          ('Sans','arial.ttf'),('Mono','consola.ttf')]:
            pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
        self.w,self.height=A4
        self.x=48
        self.width=self.w-2*self.x
        self.c=Canvas(str(path),pagesize=A4,pageCompression=1)
        self.c.setTitle('Управление ресурсами в Kubernetes. Лабораторная работа № 5')
        self.c.setAuthor('Карташов Игорь Олегович')
        self.no=0
        self.y=0

    def page(self,title=None):
        if self.no:
            assert self.y>=43, (self.no,self.y)
            self.c.showPage()
        self.no+=1
        self.y=self.height-53
        if title:
            self.p(title,'Bold',20,24,14)

    def p(self,markup,font='Body',size=12,leading=16,gap=9,align=0):
        style=ParagraphStyle('p',fontName=font,fontSize=size,leading=leading,alignment=align,
                             textColor=colors.HexColor('#18212b'))
        para=Paragraph(markup,style)
        _,height=para.wrap(self.width,800)
        self.y-=height
        para.drawOn(self.c,self.x,self.y)
        self.y-=gap

    def h(self,title):
        self.p(title,'Bold',14,18,6)

    def table(self,headers,rows,widths,size=10.5):
        assert abs(sum(widths)-self.width)<1
        def cell(s,bold=False):
            return Paragraph(escape(str(s)),ParagraphStyle('t',fontName='Bold' if bold else 'Body',
                             fontSize=size,leading=size+2.6,textColor=colors.HexColor('#18212b')))
        data=[[cell(s,True) for s in headers]]+[[cell(s) for s in row] for row in rows]
        tab=Table(data,colWidths=widths,hAlign='LEFT')
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7edf2')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),6),
            ('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),
            ('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,-1),.35,colors.HexColor('#b5c1ca'))]))
        _,height=tab.wrap(self.width,1000)
        self.y-=height
        tab.drawOn(self.c,self.x,self.y)
        self.y-=12

    def shot(self,name,caption):
        image=ImageReader(str(ROOT/'evidence/screenshots'/f'{name}.png'))
        iw,ih=image.getSize()
        height=self.width*ih/iw
        self.y-=height
        self.c.drawImage(image,self.x,self.y,width=self.width,height=height)
        self.y-=6
        self.p(caption,'Italic',10.5,13,9)

    def footer(self):
        self.c.setFont('Sans',9)
        self.c.setFillColor(colors.HexColor('#485866'))
        self.c.drawCentredString(self.w/2,27,str(self.no))


def main():
    mem=load('evidence/memory.json')
    sched=load('evidence/scheduling.json')
    quota=load('evidence/quota-result.json')
    mig=load('evidence/migration.json')
    idx=[json.loads(s) for s in (ROOT/'evidence/pairs-index.log').read_text(encoding='utf-8').splitlines()][-1]
    spans=load('evidence/map-overlap.json')
    val=load('results/verification.json')
    original=load('evidence/original-comparison.json')
    profile,tuned=mem['profile'],mem['tuned']
    peak=profile['cgroup_peak_bytes']/2**20
    overlap=duration(max(s['start'] for s in spans),min(s['end'] for s in spans))
    assert val['full_csv_equal'] and len(mig)==4 and len(val['top10'])==10 and overlap>0
    path=ROOT/'output/pdf/Карташов_Игорь_J3312_Kubernetes.pdf'
    path.parent.mkdir(parents=True,exist_ok=True)
    r=Report(path)
    w=r.width
    r.page()
    r.p('Университет ИТМО','Body',16,20,5,TA_CENTER)
    r.p('Инженерия данных','Body',13,17,0,TA_CENTER)
    r.y-=145
    r.p('ОТЧЁТ ПО ЛАБОРАТОРНОЙ РАБОТЕ № 5','Bold',18,23,13,TA_CENTER)
    r.p('Управление ресурсами в Kubernetes','Bold',23,29,12,TA_CENTER)
    r.p('Вариант 1. Программист, разработчик на 1С','Body',14,19,0,TA_CENTER)
    r.y-=126
    r.p('Карташов Игорь Олегович','Body',14,18,3,TA_RIGHT)
    r.p('Группа J3312','Body',14,18,0,TA_RIGHT)
    r.y=92
    r.p('Санкт-Петербург, 2026','Body',12,15,0,TA_CENTER)

    r.page('1. Запуск программы и предел памяти')
    r.p('На своём компьютере я поднял один узел Kubernetes v1.34.0 в Ubuntu 22.04 под WSL2. Для кластера использовал kind v0.30.0 и Docker Engine 28.4.0. Собрал образ skills-1c:lab5 и загрузил его на узел. В первом опыте Job читал полный CSV из каталога, подключённого только для чтения.')
    r.p('Из ДЗ № 3 взял отбор вакансий и подсчёт неупорядоченных пар. Оставил роль «Программист, разработчик». В названии искал «1С» с русской или латинской буквой и упоминание профессии — «программист», «разработчик», developer или programmer. Регистр букв не учитывал. Исключил Битрикс, Bitrix и Java Developer. Навыки привёл к нижнему регистру, убрал пробелы по краям и повторы внутри вакансии.')
    r.table(['Job','Заявка RAM','Предел RAM','Результат контейнера'],[
        ['pairs-oom','8 МиБ','12 МиБ','OOMKilled, код 137'],
        ['pairs-profile','64 МиБ','768 МиБ',f'Completed, пик {dec(peak)} МиБ'],
        ['pairs-tuned',f"{mem['request_mib']} МиБ",f"{mem['limit_mib']} МиБ",f"Completed, пик {dec(tuned['cgroup_peak_bytes']/2**20)} МиБ"]],
        [108,94,95,w-297])
    r.p(f"Во всех трёх Job заявка составила 250m CPU, предел — 1 CPU. Пробный расчёт уложился в 24 МиБ. При 12 МиБ ядро завершило контейнер. Затем я поднял предел и прочитал memory.peak из cgroup после расчёта. Получилось {n(profile['cgroup_peak_bytes'])} байт. С запасом в 25 % это {dec(peak)} × 1,25 ≈ {dec(peak*1.25)} МиБ. Я округлил вверх до ближайших 16 МиБ и поставил {mem['limit_mib']} МиБ. С этим пределом Job завершился с кодом 0.")
    r.shot('memory','Рисунок 1. Узел и состояние контейнера после каждого из трёх запусков.')
    r.footer()

    r.page('2. RustFS внутри кластера')
    r.p('Для RustFS 1.0.3 создал StatefulSet с одним Pod и четырьмя постоянными томами по 1 ГиБ. Каждый том смонтировал в свой каталог. Сохранил схему из ДЗ № 2 с двумя фрагментами данных и двумя фрагментами чётности. Все четыре тома находятся на одном компьютере.')
    r.p('Из прежнего RustFS прочитал три исходных объекта ДЗ № 2 и CSV для расчёта из ДЗ № 3. Сохранил имена бакетов и ключи. После загрузки повторно скачал каждый объект уже из кластера и сверил SHA-256 с исходным.')
    r.table(['Бакет','Ключ объекта','Размер, байт'],[[o['bucket'],o['key'],n(o['bytes'])] for o in mig],
            [92,254,w-346])
    r.p('Клиенты в Pod обращались к S3 через внутренний Service rustfs в пространстве skills-1c. Для переноса с Windows я временно пробросил порт Service на localhost. Во время параллельного расчёта исходный файл читался через сеть кластера.')
    r.shot('storage','Рисунок 2. Четыре привязанных PVC и завершённые задания индексации, подсчёта и объединения.')
    r.footer()

    r.page('3. Параллельный расчёт и сверка с ДЗ № 3')
    r.p('Сначала один Job прочитал CSV и записал в S3 смещения конца полных записей. Затем запустил Indexed Job с completions=4 и parallelism=4. Каждый Pod взял свой индекс и запросил свой диапазон байтов через S3 Range GET. Заголовок общий, диапазоны начинаются с первой записи данных. Все четыре ответа имели статус HTTP 206.')
    r.table(['Индекс','Байты включительно','Вакансий','Отобрано'],[
        [s['index'],f"{n(part['start'])} – {n(part['end'])}",n(s['result']['rows']),n(s['result']['selected'])]
        for s,part in zip(spans,idx['ranges'])],[52,209,112,w-373])
    r.p(f"По журналам все четыре процесса работали одновременно {dec(overlap,2)} с. Каждый записал в S3 полный счётчик своей части. Последний Job сложил частоты одинаковых пар и отсортировал результат. Из {n(val['rows'])} вакансий условию соответствовали {n(val['selected'])}. Получилось {n(val['occurrences'])} вхождений и {n(val['unique'])} разных пар.")
    r.h('Десять самых частых пар')
    r.table(['№','Первый навык','Второй навык','ДЗ № 3','K8s'],[
        [x['rank'],x['skill_1'],x['skill_2'],n(x['lab3']),n(x['kubernetes'])] for x in val['top10']],
        [29,145,197,65,w-436],size=10.3)
    r.p(f"Скачал итоговый CSV и побайтно сравнил его с таблицей из ДЗ № 3. Совпали все {n(val['bytes'])} байта. Одиночный Job получил ту же сумму SHA-256.",gap=4)
    r.p(escape(val['sha256']),'Mono',9,12,0)
    r.y-=10
    r.p(f"Для проверки запустил в кластере и исходный MapReduce из ДЗ № 3 без изменений. Он считает одиночные навыки, пары и тройки четырьмя процессами. В ДЗ № 3 наибольший суммарный RSS за три запуска был {dec(original['old_rss_max_mib'])} МиБ. Тем же правилом с запасом 25 % получил предел {original['limit_mib']} МиБ. В Kubernetes пик cgroup этой версии составил {dec(original['result']['cgroup_peak_bytes']/2**20)} МиБ, таблица пар совпала с эталоном.",size=11.3,leading=14.5,gap=0)
    r.footer()

    r.page('4. Процессор, приоритет и квота')
    r.h('Когда запросу не хватает CPU')
    r.p(f"На узле было 16 CPU. В заявках 1000m соответствует одному CPU. До опыта было запрошено {n(sched['initial_requests_m'])}m. Первой задаче я задал ещё {n(sched['holder_request_m'])}m, осталось 500m. Вторая запросила 1 CPU и осталась в Pending с событием FailedScheduling и причиной Insufficient cpu. После удаления первой задачи тот же Pod перешёл в Running. Планировщик учитывал заявки, хотя оба процесса ждали в sleep.")
    r.shot('cpu','Рисунок 3. Причина ожидания и состояния одного Pod до и после освобождения CPU.')
    r.h('Как высокий приоритет освободил место')
    r.p(f"Повторил опыт с теми же заявками. Первой задаче назначил приоритет {sched['low_priority']}, второй — {sched['high_priority']}. Планировщик вытеснил {sched['low']}, и {sched['high']} перешёл в Running. После удаления задачи с высоким приоритетом первый Job продолжил работу уже в новом Pod {sched['low_replacement']}.")
    r.h('Что ограничила квота')
    r.p('В отдельном пространстве skills-quota ограничил сумму requests.cpu одним ядром. Первый Pod занял 750m. При создании второго потребовалось ещё 500m. Сумма 1250m превысила квоту, и API вернул Forbidden с сообщением exceeded quota. Второй Pod появился только после того, как я удалил первый и повторил тот же запрос.')
    r.shot('scheduler','Рисунок 4. Событие вытеснения и повторная попытка создать Pod сверх квоты.')
    r.footer()

    r.page('5. Сравнение YARN, Mesos и Kubernetes')
    r.p('Все три системы позволяют нескольким приложениям делить процессоры и память одних машин. На примере своего расчёта я сравнил, кто выбирает узел для очередной задачи и кто следит за её завершением.')
    r.h('YARN')
    r.p('ResourceManager ведёт учёт ресурсов кластера и выделяет их приложениям. ApplicationMaster запрашивает ресурсы под задачи своего приложения, NodeManager на выбранном узле запускает контейнеры. Для Hadoop MapReduce уже есть ApplicationMaster, который распределяет map- и reduce-задачи и повторяет неудачные попытки. Очереди позволяют поделить ресурсы между командами. Для программы со своим порядком запуска потребуется подходящий фреймворк или собственный ApplicationMaster.')
    r.h('Mesos')
    r.p('В Mesos два уровня планирования. Master предлагает фреймворку ресурсы конкретных агентов. Планировщик фреймворка выбирает задачи под предложение или ждёт следующего, а на агенте их выполняет executor. Свои правила размещения удобны, когда приложениям нужны разные типы узлов. Обработку предложений и повторный запуск задач должен обеспечить сам фреймворк. Для нового кластера я также учитывал бы, что с 2025 года проект находится в архиве <link href="https://attic.apache.org/projects/mesos.html" color="#185283">Apache Attic</link>.')
    r.h('Kubernetes')
    r.p('В Kubernetes я указал ресурсы в описании Pod, а kube-scheduler сам подобрал узел. Контроллер Job следил за завершением четырёх индексов, kubelet запускал контейнеры на узле. Для этой работы мне удобно, что долгоживущее S3 и короткие вычисления описываются в одном кластере. При этом порядок стадий, границы CSV и объединение частот пришлось задать в программе и сценарии запуска.')
    r.p('Для своего расчёта я бы оставил Kubernetes. Один манифест задаёт число параллельных исполнителей, а RustFS остаётся доступен по одному имени, пока меняются Pod вычислений. Если бы данные уже лежали в HDFS и расчёт был написан для Hadoop MapReduce, я бы выбрал YARN с готовой очередью заданий.')
    r.p('<link href="https://github.com/IGK-arch/itmo-kubernetes-1c" color="#185283">Репозиторий работы · github.com/IGK-arch/itmo-kubernetes-1c</link>','Sans',10.3,15,0)
    r.footer()
    assert r.y>=43
    r.c.save()
    print(path)


if __name__=='__main__':
    main()
