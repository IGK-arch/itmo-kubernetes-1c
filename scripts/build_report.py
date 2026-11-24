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
    r.p('На своём компьютере я поднял одноузловой кластер Kubernetes 1.34.0 с помощью kind 0.30.0. Кластер работал в Ubuntu 22.04 под WSL2, версия Docker Engine — 28.4.0. Собрал образ skills-1c:lab5, загрузил его в kind и запустил Job. Для опыта с памятью подключил каталог с исходным CSV только для чтения.')
    r.p('Фильтр взял из ДЗ № 3. Оставил вакансии с ролью «Программист, разработчик». В названии искал одновременно «1С» (с русской или латинской буквой) и упоминание профессии — «программист», «разработчик», developer или programmer. Регистр не учитывал. Вакансии с упоминанием «Битрикс», Bitrix или Java Developer пропустил. Навыки привёл к нижнему регистру и убрал пробелы по краям. Каждую пару учитывал один раз на вакансию.')
    r.table(['Job','Заявка RAM','Предел RAM','Результат контейнера'],[
        ['pairs-oom','8 МиБ','12 МиБ','OOMKilled, код 137'],
        ['pairs-profile','64 МиБ','768 МиБ',f'Completed, пик {dec(peak,2)} МиБ'],
        ['pairs-tuned',f"{mem['request_mib']} МиБ",f"{mem['limit_mib']} МиБ",f"Completed, пик {dec(tuned['cgroup_peak_bytes']/2**20,2)} МиБ"]],
        [108,94,95,w-297])
    r.p(f"Для каждого Job задал заявку 250m CPU и предел 1 CPU. Пробный запуск при 24 МиБ прошёл. При 12 МиБ контейнер получил OOMKilled. Для замера поднял предел до 768 МиБ. Счётчик memory.peak в cgroup показал {n(profile['cgroup_peak_bytes'])} байт, или {dec(peak,2)} МиБ. С запасом в 25 % получилось {dec(peak,2)} × 1,25 ≈ {dec(peak*1.25,2)} МиБ. Округлил вверх до числа, кратного 16, и получил {mem['limit_mib']} МиБ. С этим пределом расчёт завершился с кодом 0.")
    r.shot('memory','Рисунок 1. Узел и состояние контейнера после каждого из трёх запусков.')
    r.p(f"Отдельно запустил исходную программу ДЗ № 3 без изменений. Она считает одиночные навыки, пары и тройки в четырёх процессах. В ДЗ № 3 максимальная сумма RSS процессов за три запуска составила {dec(original['old_rss_max_mib'])} МиБ. По тому же правилу получил предел {original['limit_mib']} МиБ. В Kubernetes пик памяти контейнера составил {dec(original['result']['cgroup_peak_bytes']/2**20)} МиБ. Таблица пар совпала с результатом ДЗ № 3.",gap=0)
    r.footer()

    r.page('2. RustFS внутри кластера')
    r.p('В кластере я развернул RustFS 1.0.3 как StatefulSet с одним Pod. Подключил четыре постоянных тома по 1 ГиБ, каждый в отдельный каталог. Оставил схему 2+2 из ДЗ № 2. Для каждого блока RustFS записывает два фрагмента данных и два фрагмента чётности. Физически все тома лежат на одном компьютере.')
    r.p('Из прежнего RustFS перенёс три объекта ДЗ № 2 и CSV с вакансиями для ДЗ № 3. Имена бакетов и ключи сохранил. Скачал все четыре объекта из нового хранилища и сравнил их SHA-256 с исходными. Все суммы совпали.')
    r.table(['Бакет','Ключ объекта','Размер, байт'],[[o['bucket'],o['key'],n(o['bytes'])] for o in mig],
            [92,254,w-346])
    r.p('Для копирования с Windows я временно пробросил порт RustFS на localhost. При параллельном расчёте Pod обращались к RustFS напрямую через внутренний Service в пространстве имён skills-1c.')
    r.shot('storage','Рисунок 2. Четыре привязанных PVC и завершённые задания индексации, подсчёта и объединения.')
    r.footer()

    r.page('3. Параллельный расчёт и сверка с ДЗ № 3')
    r.p(f"Сначала один Job прочитал CSV и сохранил в S3 границы полных записей. Заголовок занял первые {idx['ranges'][0]['start']} байта. Переносы строк внутри полей учитывались, поэтому каждая вакансия целиком попала в один диапазон. Затем я запустил Indexed Job с completions=4 и parallelism=4. Каждый Pod запросил свой диапазон через S3 Range GET и получил HTTP 206.")
    r.table(['Индекс','Байты включительно','Вакансий','Отобрано'],[
        [s['index'],f"{n(part['start'])} – {n(part['end'])}",n(s['result']['rows']),n(s['result']['selected'])]
        for s,part in zip(spans,idx['ranges'])],[52,209,112,w-373])
    r.p(f"От старта последнего из четырёх процессов до записи первого частичного результата прошло {dec(overlap,2)} с. Каждый Pod сохранил в S3 частоты всех пар своей части. Последний Job сложил их. Из {n(val['rows'])} вакансий отбор прошли {n(val['selected'])}. Получилось {n(val['unique'])} разных пар и {n(val['occurrences'])} вхождений.")
    r.h('Десять самых частых пар по числу вакансий')
    r.table(['№','Первый навык','Второй навык','ДЗ № 3','Kubernetes'],[
        [x['rank'],x['skill_1'],x['skill_2'],n(x['lab3']),n(x['kubernetes'])] for x in val['top10']],
        [29,145,197,65,w-436],size=10.3)
    r.p(f"Побайтно сравнил CSV из RustFS с результатом ДЗ № 3. Совпали все {n(val['bytes'])} байта.",gap=6)
    r.shot('result','Рисунок 3. Размер итогового файла, его SHA-256 и результат сравнения командой cmp.')
    r.footer()

    r.page('4. Процессор, приоритет и квота')
    r.h('Ожидание свободного CPU')
    r.p(f"На узле было {sched['allocatable_m']//1000} CPU (1000m = 1 CPU). Другие Pod уже запросили {n(sched['initial_requests_m'])}m. После заявки первой задачи на {n(sched['holder_request_m'])}m осталось {sched['free_m']-sched['holder_request_m']}m. Вторая запросила {sched['waiting_request_m']}m и осталась в Pending. В событии FailedScheduling планировщик указал причину Insufficient cpu. Когда я удалил первую задачу, тот же Pod перешёл в Running. Обе задачи выполняли sleep, поэтому ожидание определялось размером заявок.")
    r.shot('cpu','Рисунок 4. Один и тот же Pod до и после освобождения CPU.')
    r.h('Вытеснение по приоритету')
    r.p(f"Оставил прежние заявки, но первой задаче назначил приоритет {sched['low_priority']}, а второй — {sched['high_priority']}. Планировщик вытеснил {sched['low']} и освободил место для {sched['high']}. Когда я удалил задачу с высоким приоритетом, у первого Job запустился новый Pod {sched['low_replacement']}. В нём процесс начал работу заново.")
    r.h('Квота пространства имён')
    r.p(f"В пространстве {quota['namespace']} ограничил сумму заявок requests.cpu одним CPU. Первый Pod запросил {quota['used_m']}m, второй — ещё {quota['request_m']}m. В сумме вышло {quota['used_m']+quota['request_m']}m. API отклонил создание второго Pod с ошибкой Forbidden (exceeded quota). Я удалил первый Pod и отправил тот же манифест ещё раз. На этот раз второй Pod перешёл в {quota['after_release']}.")
    r.shot('scheduler','Рисунок 5. Событие Preempted и ответ API при превышении квоты.')
    r.footer()

    r.page('5. Сравнение YARN, Mesos и Kubernetes')
    r.p('Все три системы делят CPU и память узлов между приложениями. На примере моего CSV разница видна в том, кто получит ресурсы под очередную часть файла и кто повторит задачу, если она упадёт.')
    r.h('YARN')
    r.p('В YARN у каждого приложения есть ApplicationMaster. Он запрашивает контейнеры у ResourceManager, а NodeManager запускает их на выделенных узлах. Для Hadoop MapReduce уже реализованы стадии map и reduce и повтор неудачных задач. В общем кластере команды могут делить ресурсы через очереди. Для программы со своим порядком запуска понадобится подходящий фреймворк для YARN или собственный ApplicationMaster.')
    r.h('Mesos')
    r.p('В Mesos два уровня планирования. Master предлагает ресурсы конкретного агента, а планировщик фреймворка решает, какие задачи отправить на этот узел. На агенте их выполняет executor. Фреймворк может подождать предложения от узла, на котором лежат нужные данные. Если готового фреймворка нет, обработку предложений и повтор задач при сбое придётся написать самому. С 2025 года проект находится в <link href="https://attic.apache.org/projects/mesos.html" color="#185283">архиве Apache</link>.')
    r.h('Kubernetes')
    r.p('В Kubernetes я указал заявки в манифесте Pod. Узел выбирал kube-scheduler, контейнеры на нём запускал kubelet. Контроллер Job следил за завершением всех четырёх частей. В опыте с вытеснением он же создал новый Pod для прерванной задачи. Деление CSV по границам записей и сложение частот я написал сам, а порядок запуска стадий задал в сценарии.')
    r.p('Для этой работы я бы выбрал Kubernetes. RustFS доступен по одному имени, а число Pod для расчёта можно менять в манифесте Job. Если бы данные уже лежали в HDFS и программа была написана для Hadoop MapReduce, я бы оставил её на YARN — там распределение map- и reduce-задач уже готово.')
    r.p('<link href="https://github.com/IGK-arch/itmo-kubernetes-1c" color="#185283">Репозиторий работы · github.com/IGK-arch/itmo-kubernetes-1c</link>','Sans',10.3,15,0)
    r.footer()
    assert r.y>=43
    r.c.save()
    print(path)


if __name__=='__main__':
    main()
