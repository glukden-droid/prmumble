# Mumble-сервер Project Reality на Mumble 1.5

[English](README.md) | **Русский**

Голосовой сервер для игровых серверов Project Reality: BF2. Заменяет старый
PRMurmur 1.2 (2013 год) на Mumble 1.5.857 с доработками PR и mumo с модулем
prbf2, который раскладывает игроков по каналам команд и отрядов.

- **Linux** — Docker-образ (`mumble-server.Dockerfile`, `docker-compose.yaml`).
- **Windows** — готовый архив без установки, собирается на GitHub Actions
  (`.github/workflows/windows-build.yml`), инструкция внутри архива на двух
  языках.

## Содержание

1. [Было и стало](#1-было-и-стало)
2. [Доработки PR в сервере](#2-доработки-pr-в-сервере)
3. [Каналы и ACL](#3-каналы-и-acl)
4. [Боты](#4-боты)
5. [Правки prbf2.py](#5-правки-prbf2py)
6. [Проверка подписи (secret)](#6-проверка-подписи-secret)
7. [Установка на Linux (Docker)](#7-установка-на-linux-docker)
8. [Windows](#8-windows)
9. [Диагностика](#9-диагностика)
10. [Состав проекта](#10-состав-проекта)

## 1. Было и стало

| | Было | Стало |
|---|---|---|
| Сервер | PRMurmur 1.2 (2013), доработанный PR | Mumble 1.5.857 из исходников + патч PR |
| Образ | Debian 10, Qt4, libssl 1.0.0 из снапшотов | Ubuntu 24.04 |
| Ice | 3.4.2 из `.deb` | 3.7, `python3-zeroc-ice` |
| slice | `PRMurmur.ice`, модуль `Murmur` | `MumbleServer.ice`, модуль `MumbleServer` |
| mumo | форк на Python 2.6 | upstream на Python 3 |
| Логика PR | `prbf2.py` | она же на Python 3, с исправлениями |
| Каналы | вручную / старая база | создаются скриптом по `games.txt` |

Клиент — Mumble 1.3.0 из комплекта PR (PRMumble), он не меняется.

## 2. Доработки PR в сервере

Стоковый Mumble не умеет того, на чём держится HUD PR, а в Ubuntu 24.04 лежит
1.5.517 — релиз-кандидат. Поэтому сервер собирается из исходников 1.5.857, и
на них накладывается `docs/patch_identity.py`.

**Как работает HUD PR** (кто говорит рядом и по рации). Разобрано по
`prmurmurd.x64` (Ghidra), `mumble_app.dll` из PRMumble и лаунчеру
`Reality.BF2.dll`:

1. PRMumble (класс `RealityData`) пишет в общую память `PRMumbleSharedData1`
   записи об игроках своего и связанных каналов: ник, канал, состояние речи,
   два флага, x y z.
2. Ник берётся из поля `"name"` plugin identity игрока, позиция — из поля
   `position` его `UserState`.
3. Лаунчер показывает игрока, если тот говорит, позиция не 0,0,0, а для
   местного голоса — не дальше 70 м от вас.

**Что делал PRMurmur и чего нет в стоковом Mumble 1.5** — это и есть патч:

| Доработка | Зачем |
|---|---|
| plugin identity рассылается всем клиентам, в том числе в начальном списке при подключении | ник для HUD (стоковый Mumble держит identity только на сервере) |
| `UserState` поле 20 = `repeated float position`, сервер пересылает его только команде отправителя | позиция для HUD; клиент PR сам шлёт свою игровую позицию. В 1.5 номер 20 был у `temporary_access_tokens`, они перенесены на 120 |

**Позиция уходит только своей команде.** PRMurmur рассылал позицию каждого
игрока всем, и изменённый клиент мог собрать радар противника. Здесь позиция
уходит только игрокам в канале отправителя и в связанных с ним, то есть его
команде. HUD читает ровно их, а союзников игра и так показывает на карте.

Контекст плагина (ip:port сервера) по-прежнему никому не пересылается, как и в
PRMurmur. Identity уходит целиком, с hash и pass, — так было и раньше.

**Особенность 1.5 с заглушением.** `Server::clearACLCache` при каждом
изменении групп рассылает клиентам `suppress=true`, даже когда право говорить
вернулось. Раньше mumo каждые ~20 с снимал и возвращал группы, и у игроков
выключался микрофон. Обход — в `prbf2.py` (раздел 5).

## 3. Каналы и ACL

`scripts/setup_channels.py` строит дерево через Ice на пустом сервере по
списку игровых серверов (`games.txt`) и сам пишет карту каналов для mumo
(`prbf2.ini`), так что номера всегда совпадают.

```
Root
  Lobby                                  defaultchannel=1
  PR BF2 Game Servers
    <сервер>                             сюда mumo выводит вышедших из игры
      Team 1 (opfor) / Team 2 (blufor)   связан с Commander и отрядами
        Commander, No Squad, Squad 1..9
```

`games.txt` — одна строка на игровой сервер:

```
main0 | [RU] Мой PR сервер | 203.0.113.10:16567
```

ACL повторяют `prbf2man.py` из старой сборки: в каналы команд и отрядов сам
никто не входит, туда переносит mumo по команде и отряду из игры. Говорить
могут только игроки этой игры, отряд слышит свой канал, командир и сквадные
шепчут по связанным каналам. Прослушивание чужих каналов (Listen) и временные
каналы запрещены всем, кроме групп `admin` и `bots`. Слушатели включены
(`listenersperchannel=-1`); клиент 1.3 из-за этого показывает предупреждение.

Как в PRMurmur, в Lobby никто не говорит (писать в чат можно); говорить
там могут только админы и боты.

Строки `not allowed to Enter in Squad N` в логе сервера нормальны: клиент PR
сам пытается войти в отряд, сервер отказывает, mumo переносит.

## 4. Боты

Группа `bots` на корне (запись, музыка, ретрансляция): входить в любой канал,
слушать, говорить, шептать, писать в чат, заглушать других. Бот подключается
с клиентским сертификатом, затем:

```bash
sudo docker exec prmurmur15 python3 /opt/scripts/grant_bot.py <ник бота>
```

Скрипт регистрирует бота по сертификату, добавляет в `bots` и ставит
разрешения на корне, в каналах игровых серверов и команд (после `all deny`).
После первой регистрации бота нужно переподключить. mumo ботов не трогает.

### Сброс прав

`reset_acl.py` возвращает ACL всех каналов и связи команд к тому, что ставит
`setup_channels.py` на новом сервере, без пересоздания каналов: регистрации,
админы, баны и боты сохраняются. Пригодится после ручных правок ACL или если
игроки слышат не тех. После сброса перезапустите контейнер, чтобы mumo снова
выдал игрокам группы.

```bash
sudo docker exec prmurmur15 python3 /opt/scripts/reset_acl.py --dry-run   # что изменится
sudo docker exec prmurmur15 python3 /opt/scripts/reset_acl.py
sudo docker restart prmurmur15
```

### Местный голос между командами

Обычную (местную) речь можно сделать слышной и противнику; клиент PR
затухает её по расстоянию, поэтому слышат только враги рядом. Для этого
связываются Team 1 и Team 2 игрового сервера (как `--linkteams` в старом
`prbf2man.py`). Рация отрядов и командирские каналы не затрагиваются, а
позиции игроков для HUD по-прежнему уходят только своей команде.

```bash
sudo docker exec prmurmur15 python3 /opt/scripts/link_teams.py status
sudo docker exec prmurmur15 python3 /opt/scripts/link_teams.py on main0    # или: on (все)
sudo docker exec prmurmur15 python3 /opt/scripts/link_teams.py off main0
```

Настройка хранится в базе и переживает перезапуск.

## 5. Правки prbf2.py

Порт на Python 3 (`docs/port_prbf2.py`) плюс то, что нашлось в работе:

| Что | Почему |
|---|---|
| `decodeContext` | Mumble 1.5 отдаёт контекст плагина через Ice в base64; без раскодирования игрок считался «не в игре» |
| группы по разнице (`player_groups`) | на новый `pass` без смены отряда группы не трогаются; новые добавляются раньше, чем снимаются старые |
| явная синхронизация `suppress` | после переноса и смены групп клиентам уходит правильное значение |
| `log.exception` вместо `sys.exc_traceback` | в Python 3 его нет, ошибки пропадали молча |
| `x2bool` из `config` | в upstream mumo он переехал |

## 6. Проверка подписи (secret)

Игровой сервер раз в 30 секунд выдаёт каждому своему игроку одноразовый
пароль `sha1(минута + hash + mum_mumbleSecret)`; клиент PR передаёт его в
Mumble в identity, mumo сверяет со своим `secret`. Игрок, которого нет на
ваших игровых серверах, свежего пароля не получает, и за минуту-две mumo
выводит его из каналов команд и отрядов — даже если клиент продолжает
присылать старые данные игры (например, после перехода на другой сервер).

Проверено 2026-10-10 на полном сервере: пароли клиентов совпадают с теми, что
считает игровой сервер, отказов 0.

Значение — то же, что `mum_mumbleSecret` в `realityconfig_admin.py` **всех**
игровых серверов из `games.txt`:

- новая установка: положить его в `data/secret.txt` до `initialsetup.sh`;
- работающий сервер: `secret = <значение>` в
  `data/mumo/modules-enabled/prbf2.ini`, затем `sudo docker restart prmurmur15`.

Пустой `secret` выключает проверку. Сразу после входа игрок может до 30 секунд
постоять в канале сервера, пока не придёт первый пароль.

## 7. Установка на Linux (Docker)

Нужен Linux с Docker и плагином compose (`docker compose version`).
Контейнер работает в `network_mode: host`: сервер слушает 64740, Ice — только
127.0.0.1:6504.

**Шаг 1 — получить код**

```bash
git clone https://github.com/glukden-droid/prmumble.git && cd prmumble
```

**Шаг 2 — свои игровые серверы.** По строке на игровой сервер:
`имя | название канала | ip:порт` (ip:порт — адрес, по которому игроки
заходят на ИГРОВОЙ сервер).

```bash
mkdir -p data && cp config/games.txt data/games.txt
nano data/games.txt
echo 'значение mum_mumbleSecret' > data/secret.txt   # см. раздел 6
```

**Шаг 3 — сборка, запуск, создание каналов** (первая сборка 10–20 минут):

```bash
sudo bash scripts/initialsetup.sh
```

В конце должно быть `setup: ... channels, map written ...` и
`createchannel: done`.

**Шаг 4 — пароль SuperUser**

```bash
sudo docker exec prmurmur15 mumble-server -ini /data/mumble-server.ini -supw 'НадёжныйПароль'
```

**Шаг 5 — брандмауэр.** Открыть игрокам 64740 TCP и UDP; 6504 не открывать
никогда.

```bash
sudo ufw allow 64740/tcp && sudo ufw allow 64740/udp
```

**Шаг 6 — админы.** Админ один раз подключается своим клиентом и
регистрируется (правый клик по своему имени → Зарегистрироваться). Затем под
`SuperUser`: правый клик по Root → Изменить → Группы → `admin` → добавить его.

**Шаг 7 — проверка.** Зайдите в Project Reality на один из своих серверов;
клиент PR Mumble должен за пару секунд перенести вас в канал отряда.

```bash
sudo docker logs prmurmur15 2>&1 | grep -E "running on|ServerCallback" | tail -2
sudo docker exec prmurmur15 python3 /opt/scripts/check_acl.py <часть ника>
```

По желанию: боты и местный голос между командами (раздел 4).

**Повседневная работа**

| Задача | Команда |
|---|---|
| состояние / логи | `sudo docker ps`, `sudo docker logs -f prmurmur15`, `sudo tail -f data/logs/mumo.log` |
| перезапуск | `sudo docker compose restart` |
| остановить / запустить | `sudo docker compose down` / `sudo docker compose up -d` |
| обновить код | `git pull && sudo docker compose build && sudo docker compose up -d` |
| права по умолчанию | `sudo docker exec prmurmur15 python3 /opt/scripts/reset_acl.py && sudo docker restart prmurmur15` |
| начать заново (новые каналы) | `sudo docker compose down && sudo mv data data.old`, затем шаги 2–6 |
| резервная копия | скопировать `data/` (база, конфиги, логи) |

Нюансы:
- секрет Ice (`prmurmurpassword` в `data/mumble-server.ini` и
  `data/mumo/mumo.ini`) можно оставить: Ice слушает только 127.0.0.1. Если
  меняете — одинаково в обоих файлах и перезапуск;
- контейнер отдаёт `/data` пользователю `mumble-server` (uid 101), файлы в
  `data/` с хоста правятся через `sudo`;
- если порты Ice в двух файлах разные, mumo пишет `Server refused
  connection`, и контейнер перезапускается по кругу;
- `data/` нет в git, `git pull` её не трогает.

## 8. Windows

Архив `PRMumble-Server-1.5.857-win64.zip`: тот же сервер с патчем PR,
встроенный Python 3.11 с Ice, mumo с prbf2, скрипты и `.bat` (`start`, `stop`,
`setup-channels`, `grant-bot`, `check-acl`, `link-teams`, `reset-acl`,
`set-superuser-password`). Ничего
устанавливать не нужно. Инструкция внутри: `README_RU.txt` и `README_EN.txt`.

Скачать: [Releases](../../releases) (`PRMumble-Server-1.5.857-win64.zip`).
Собрать самому: Actions → `windows-build` → Run workflow; архив — артефакт
запуска.
Используется готовое окружение проекта Mumble (vcpkg
`x64-windows-static-md`, MSVC). Сборка сама проверяет пакет: сервер, Ice,
создание каналов, запуск mumo с prbf2. Исходники пакета — `windows/package/`.
Скрипты берут пути из переменных `PRMUMBLE_*`, без них — пути Docker.

## 9. Диагностика

| Команда | Что показывает |
|---|---|
| `sudo docker exec prmurmur15 python3 /opt/scripts/check_acl.py <ник>` | права игрока во всех каналах |
| `sudo docker exec prmurmur15 python3 /opt/scripts/voice_probe.py 60` | бот слушает самый людный отряд: тип речи и есть ли позиция в голосе (нужен `pymumble`) |
| `sudo tail -n 50 data/logs/mumo.log` | что делает mumo (`level = 10` в `mumo.ini` — подробно) |
| `python scripts/hud_dump.py` (на ПК с игрой) | что PRMumble отдаёт лаунчеру для HUD: ник, канал, речь, позиция |

## 10. Состав проекта

| Файл | Что |
|---|---|
| `mumble-server.Dockerfile` | сборка Mumble 1.5.857 с патчем PR, mumo, Ubuntu 24.04 |
| `docker-compose.yaml` | сервис `prmurmur15` |
| `config/mumble-server.ini`, `config/mumo.ini` | шаблоны конфигов (64740, Ice 6504) |
| `config/games.txt` | пример списка игровых серверов |
| `mumo/modules/prbf2.py` | логика PR на Python 3 |
| `docs/patch_identity.py` | патч сервера: identity и позиция для HUD |
| `docs/port_prbf2.py` | воспроизводимый перенос prbf2.py на Python 3 |
| `scripts/initialsetup.sh` | первая установка на пустой `data/` |
| `scripts/createchannel.sh` | создание каналов на работающем сервере |
| `scripts/setup_channels.py` | дерево каналов, ACL и карта для mumo (Ice) |
| `scripts/check_acl.py` | фактические права подключённых игроков |
| `scripts/grant_bot.py` | права бота: войти, слушать, говорить везде |
| `scripts/link_teams.py` | местный голос между командами: вкл/выкл |
| `scripts/reset_acl.py` | права и связи команд по умолчанию, как при установке |
| `scripts/voice_probe.py` | что сервер пересылает в голосе |
| `scripts/hud_dump.py` | что PRMumble отдаёт HUD (Windows, ПК с игрой) |
| `scripts/entrypoint.sh` | запуск сервера и mumo в контейнере |
| `windows/package/` | файлы Windows-пакета: конфиги, `.bat`, `games.txt`, инструкции |
| `.github/workflows/windows-build.yml` | сборка Windows-пакета на GitHub Actions |
