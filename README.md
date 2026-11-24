# Kubernetes и расчёт пар навыков

Карташов Игорь Олегович, ИТМО, J3312. Лабораторная работа № 5.

[Отчёт в PDF](output/pdf/Карташов_Игорь_J3312_Kubernetes.pdf) · [Итоговая десятка](results/top10.csv) · [Полная таблица пар](results/skills_2.csv).

Вариант 1 из [ДЗ № 3](https://github.com/IGK-arch/itmo-mapreduce-1c/tree/b3e6ac9d331fa38e5e29281469fdfc8a3743da9a) — программист, разработчик на 1С. Исходный CSV преподавателя содержит 229 388 вакансий и занимает 847 619 384 байта. В прежнем RustFS это объект `s3://hh-lake/raw/it_vacancies_2024.csv`. В бакете `it-vacancies` лежат три исходных объекта ДЗ № 2.

## Состав работы

- Основной Dockerfile собирает образ для расчёта пар. В `app/pairs.py` сохранены фильтр вакансий, нормализация навыков и ключи пар из ДЗ № 3. В `original/src/` лежат неизменённые модули того ДЗ. Для их отдельного запуска поверх первого образа собирается `original/Dockerfile`.
- В `manifests/` находятся применённые спецификации. JSON-манифесты можно передать в `kubectl create -f` наравне с YAML.
- В `evidence/` сохранены stdout контейнеров, статусы Job и Pod, события планировщика, результат переноса S3 и снимки терминала. Первый пробный расчёт при 24 МиБ завершился успешно, его журнал выделен в `trial-24Mi/`. При 12 МиБ контейнер получил OOMKilled.
- Эталон `reference/skills_2.csv` взят из `results/optimized-1` работы № 3. Рейтинг сортируется по убыванию частоты, при равенстве — по обоим навыкам. Полная таблица CSV отсортирована по ключам, как в ДЗ № 3.

## Повторение

На моём компьютере использованы Ubuntu 22.04 в WSL2, Docker Engine 28.4.0, kind 0.30.0, kubectl и Kubernetes 1.34.0. Для обычного Linux с работающим Docker достаточно добавить kind и kubectl. Команды ниже выполняются из корня репозитория в Bash. Для переноса данных нужны Python, boto3 и доступ к исходному S3.

```bash
mkdir -p tmp
export KUBECONFIG="$PWD/tmp/kubeconfig"
export CSV=/полный/путь/к/it_vacancies_2024.csv
python3 -m pip download --only-binary=:all: -r requirements.txt -d vendor
bash scripts/cluster.sh
bash scripts/build.sh
kind load docker-image skills-1c:lab5 --name itmo-j3312
python3 scripts/workloads.py memory
docker pull rustfs/rustfs:1.0.3
kind load docker-image rustfs/rustfs:1.0.3 --name itmo-j3312
python3 scripts/workloads.py storage
kubectl -n skills-1c port-forward --address=127.0.0.1 svc/rustfs 19021:9000
```

В следующем терминале задать тот же `KUBECONFIG`. Переменные `LEGACY_ENDPOINT`, `LEGACY_ACCESS_KEY`, `LEGACY_SECRET_KEY` указывают на прежний S3. Для кластера создаётся отдельный Secret. На моём компьютере прежний RustFS обслуживал исходные диски на порту 19020. Для запуска использовался `scripts/legacy-source.ps1` и соседняя папка ДЗ № 2.

```bash
python3 scripts/transfer.py migrate
python3 scripts/workloads.py parallel
python3 scripts/transfer.py verify
python3 scripts/scheduling.py
DOCKER_BUILDKIT=0 docker build --network=none -t skills-1c:original original
kind load docker-image skills-1c:original --name itmo-j3312
python3 scripts/original.py
python3 scripts/collect_evidence.py
python3 scripts/audit.py
```

Команды рассчитаны на новый кластер. При повторе отдельного Job сначала сохранить его журнал и удалить этот Job. Пределы памяти вычисляются по новым замерам. Для опыта с CPU скрипт считывает allocatable узла и уже занятые заявки, чтобы воспроизвести нехватку 500m.

На исходном компьютере открываю Ubuntu WSL2, перехожу в папку лабораторной и выполняю `sudo bash scripts/start-engine.sh`, затем `sudo bash scripts/cluster.sh`. Первый скрипт запускает отдельный Docker с Unix-сокетом, второй поднимает ранее созданный узел. Манифесты и данные на PVC при этом сохраняются.

### Как делится CSV

Один Pod читает исходный объект из S3. Парсер CSV определяет границы полных записей, включая записи с переводами строки в кавычках. В индекс входят длина объекта, SHA-256, ETag и четыре неперекрывающихся диапазона. Заголовок передаётся всем исполнителям отдельно. У каждого Pod Indexed Job свой JOB_COMPLETION_INDEX. Запрос Range ограничивает чтение, а If-Match связывает часть с версией исходного объекта. Для каждой части сохраняются все частоты. Редуктор читает каждый индекс один раз и суммирует одинаковые ключи.

### Память и планирование

В `pairs-profile.log` и `pairs-tuned.log` записаны пик cgroup в байтах и максимальный RSS процесса в КиБ. Для предела контейнера взят первый показатель. В опытах с процессором оба контейнера ждут в sleep, поэтому видно, как планировщик учитывает суммы заявок. В `cpu-wait-pending.txt`, `low-preempted.txt` и `quota-second-create.txt` сохранены исходные сообщения для каждого случая.

### Документация

[Ресурсы в Kubernetes](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) · [Indexed Job](https://kubernetes.io/docs/concepts/workloads/controllers/job/) · [Приоритет и вытеснение](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/) · [ResourceQuota](https://kubernetes.io/docs/concepts/policy/resource-quotas/) · [Apache YARN](https://hadoop.apache.org/docs/current/hadoop-yarn/hadoop-yarn-site/YARN.html) · [Apache Mesos](https://mesos.apache.org/documentation/latest/architecture/).
