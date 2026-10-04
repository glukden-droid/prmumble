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

Игровой сервер раз в 30 секунд шлёт клиенту одноразовый пароль
`sha1(минута + hash + mum_mumbleSecret)`, клиент передаёт его в Mumble, mumo
сверяет со своим `secret`. Проверено: сервер считает верно, mumo — по той же
формуле, но клиент PR передаёт в Mumble другие числа; старый PRMurmur тоже
писал только `Failed verifying identity`. Поэтому `secret` пустой. Если он не
пустой, mumo выводит всех игроков в канал сервера, где говорить нельзя.

## 7. Установка на Linux (Docker)

Нужны Docker с compose. Порты: 64740 TCP+UDP наружу, Ice 6504 только на
127.0.0.1 (контейнер в `network_mode: host`).

Первая установка:

```bash
git clone <этот репозиторий> prmumble && cd prmumble
mkdir -p data && cp config/games.txt data/games.txt
nano data/games.txt                       # свои игровые серверы
sudo bash scripts/initialsetup.sh         # build, up, каналы, перезапуск
sudo docker exec prmurmur15 mumble-server -ini /data/mumble-server.ini -supw 'пароль'
```

Смените секрет Ice (`icesecretread`/`icesecretwrite` в
`data/mumble-server.ini` и `secret` в `data/mumo/mumo.ini`, одинаково) и
перезапустите: `sudo docker compose restart`.

Обновление кода без потери каналов (сборка 10–20 минут при работающем
сервере, перерыв — только на перезапуск):

```bash
git pull
sudo docker compose build && sudo docker compose up -d
sudo docker logs prmurmur15 2>&1 | grep -E "running on|ServerCallback" | tail -2
```

Должно быть `Murmur 1.5.857 running on ...` и `Added Ice ServerCallback`.

Начать заново (новые каналы): `sudo docker compose down && sudo mv data
data.old`, затем первая установка.

Нюансы:
- контейнер отдаёт `/data` пользователю `mumble-server` (uid 101), файлы в
  `data/` с хоста правятся через `sudo`;
- порт Ice в `data/mumble-server.ini` и `data/mumo/mumo.ini` должен
  совпадать, иначе mumo пишет `Server refused connection` и контейнер
  перезапускается;
- состояние только в `data/`: база, конфиги, логи — это и есть резервная
  копия.

## 8. Windows

Архив `PRMumble-Server-1.5.857-win64.zip`: тот же сервер с патчем PR,
встроенный Python 3.11 с Ice, mumo с prbf2, скрипты и `.bat` (`start`, `stop`,
`setup-channels`, `grant-bot`, `check-acl`, `set-superuser-password`). Ничего
устанавливать не нужно. Инструкция внутри: `README_RU.txt` и `README_EN.txt`.

Сборка: Actions → `windows-build` → Run workflow; архив — артефакт запуска.
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
| `scripts/voice_probe.py` | что сервер пересылает в голосе |
| `scripts/hud_dump.py` | что PRMumble отдаёт HUD (Windows, ПК с игрой) |
| `scripts/entrypoint.sh` | запуск сервера и mumo в контейнере |
| `windows/package/` | файлы Windows-пакета: конфиги, `.bat`, `games.txt`, инструкции |
| `.github/workflows/windows-build.yml` | сборка Windows-пакета на GitHub Actions |
