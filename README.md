# Project Reality Mumble server on Mumble 1.5

**English** | [Русский](README.ru.md)

Voice server for Project Reality: BF2 game servers. Replaces the old
PRMurmur 1.2 (2013) with Mumble 1.5.857 plus the PR patch, and mumo with the
prbf2 module that puts players into their team and squad channels.

- **Linux** — Docker image (`mumble-server.Dockerfile`, `docker-compose.yaml`).
- **Windows** — ready-to-run archive, no installation, built on GitHub
  Actions (`.github/workflows/windows-build.yml`); the guide inside the
  archive is in English and Russian.

## Contents

1. [Before and after](#1-before-and-after)
2. [PR changes in the server](#2-pr-changes-in-the-server)
3. [Channels and ACL](#3-channels-and-acl)
4. [Bots](#4-bots)
5. [Changes in prbf2.py](#5-changes-in-prbf2py)
6. [Identity check (secret)](#6-identity-check-secret)
7. [Linux installation (Docker)](#7-linux-installation-docker)
8. [Windows](#8-windows)
9. [Diagnostics](#9-diagnostics)
10. [Project layout](#10-project-layout)

## 1. Before and after

| | Before | Now |
|---|---|---|
| Server | PRMurmur 1.2 (2013), modified by PR | Mumble 1.5.857 from source + PR patch |
| Image | Debian 10, Qt4, libssl 1.0.0 from snapshots | Ubuntu 24.04 |
| Ice | 3.4.2 from a `.deb` | 3.7, `python3-zeroc-ice` |
| slice | `PRMurmur.ice`, module `Murmur` | `MumbleServer.ice`, module `MumbleServer` |
| mumo | fork on Python 2.6 | upstream on Python 3 |
| PR logic | `prbf2.py` | same, ported to Python 3, with fixes |
| Channels | by hand / old database | created by a script from `games.txt` |

The client is the Mumble 1.3.0 that ships with PR (PRMumble); it is not
changed.

## 2. PR changes in the server

Stock Mumble lacks what the PR HUD relies on, and Ubuntu 24.04 ships 1.5.517,
a release candidate. So the server is built from the 1.5.857 sources with
`docs/patch_identity.py` applied.

**How the PR HUD works** (who is talking nearby and on the radio). Found in
`prmurmurd.x64` (Ghidra), PRMumble's `mumble_app.dll` and the launcher's
`Reality.BF2.dll`:

1. PRMumble (class `RealityData`) writes records about the players of its own
   and linked channels into the shared memory `PRMumbleSharedData1`: name,
   channel, talk state, two flags, x y z.
2. The name comes from the `"name"` field of the player's plugin identity,
   the position from the `position` field of his `UserState`.
3. The launcher shows a player if he is talking and his position is not
   0,0,0; for local voice only within 70 m of you.

**What PRMurmur did and stock Mumble 1.5 does not** — this is the patch:

| Change | Why |
|---|---|
| plugin identity is sent to all clients, also in the user list on connect | name for the HUD (stock Mumble keeps identity server-side) |
| `UserState` field 20 = `repeated float position`, relayed to the sender's team only | position for the HUD; the PR client sends its own in-game position. In 1.5 field 20 was `temporary_access_tokens`; they moved to 120 |

**Positions go to the team only.** PRMurmur broadcast every player's position
to everybody, so a modified client could build a radar of the enemy. Here the
position goes only to the users in the sender's channel and the channels
linked to it — his own team. That is exactly what the HUD reads, and
teammates see each other on the in-game map anyway.

The plugin context (game server ip:port) is still never sent to other
clients, as in PRMurmur. Identity goes out whole, with hash and pass — as
before.

**1.5 muting quirk.** `Server::clearACLCache` broadcasts `suppress=true` on
every group change, even when the player may speak again. mumo used to
remove and re-add groups every ~20 s, which muted players. Worked around in
`prbf2.py` (section 5).

## 3. Channels and ACL

`scripts/setup_channels.py` builds the tree over Ice on an empty server from
the list of game servers (`games.txt`) and writes mumo's channel map
(`prbf2.ini`) itself, so the channel ids always match.

```
Root
  Lobby                                  defaultchannel=1
  PR BF2 Game Servers
    <server>                             mumo puts players who left the game here
      Team 1 (opfor) / Team 2 (blufor)   linked to Commander and the squads
        Commander, No Squad, Squad 1..9
```

`games.txt` — one line per game server:

```
main0 | [EU] My PR Server | 203.0.113.10:16567
```

The ACLs follow `prbf2man.py` of the old setup: nobody enters team and squad
channels by himself, mumo moves players there by the team and squad reported
by the game. Only players of that game may talk; a squad hears its channel,
commander and squad leaders whisper over linked channels. Listening to other
channels (Listen) and temporary channels are denied to everyone except the
`admin` and `bots` groups. Channel listeners are enabled
(`listenersperchannel=-1`), so the 1.3 client shows a privacy warning.

`not allowed to Enter in Squad N` lines in the server log are normal: the PR
client tries to join its squad itself, the server refuses, mumo moves it.

## 4. Bots

Group `bots` on Root (recorder, music, relay): enter any channel, listen,
speak, whisper, write text, mute/deafen others. The bot connects with a
client certificate, then:

```bash
sudo docker exec prmurmur15 python3 /opt/scripts/grant_bot.py <bot name>
```

The script registers the bot under its certificate, adds it to `bots` and
sets the permissions on Root, the game server and the team channels (after
`all deny`). Reconnect the bot after its first registration. mumo leaves bots
alone.

### Cross-team local voice

Normal (local) speech can also reach the enemy team; the PR client fades it
with distance, so only enemies nearby hear it. It links Team 1 and Team 2 of
a game server (as `--linkteams` in the old `prbf2man.py`). Squad radio and
commander channels are not affected, and player positions for the HUD still
go to the own team only.

```bash
sudo docker exec prmurmur15 python3 /opt/scripts/link_teams.py status
sudo docker exec prmurmur15 python3 /opt/scripts/link_teams.py on main0    # or: on (all)
sudo docker exec prmurmur15 python3 /opt/scripts/link_teams.py off main0
```

The setting is stored in the database and survives restarts.

## 5. Changes in prbf2.py

Python 3 port (`docs/port_prbf2.py`) plus what came up in production:

| What | Why |
|---|---|
| `decodeContext` | Mumble 1.5 hands the plugin context to Ice as base64; undecoded, players counted as "not in game" |
| groups by difference (`player_groups`) | a new `pass` without a squad change does not touch groups; new groups are added before old ones are removed |
| explicit `suppress` sync | after a move or group change clients get the correct value |
| `log.exception` instead of `sys.exc_traceback` | gone in Python 3; errors were silently lost |
| `x2bool` from `config` | moved there in upstream mumo |

## 6. Identity check (secret)

Every 30 s the game server sends the client a one-time password
`sha1(minute + hash + mum_mumbleSecret)`; the client passes it to Mumble and
mumo compares it with its `secret`. Checked: the game server computes it
right, mumo uses the same formula, but the PR client passes different numbers
to Mumble; the old PRMurmur also only logged `Failed verifying identity`. So
`secret` is empty. If it is not empty, mumo moves every player into the game
server channel, where nobody can talk.

## 7. Linux installation (Docker)

Requires Docker with compose. Ports: 64740 TCP+UDP open to players, Ice 6504
on 127.0.0.1 only (the container uses `network_mode: host`).

First installation:

```bash
git clone <this repository> prmumble && cd prmumble
mkdir -p data && cp config/games.txt data/games.txt
nano data/games.txt                       # your game servers
sudo bash scripts/initialsetup.sh         # build, up, channels, restart
sudo docker exec prmurmur15 mumble-server -ini /data/mumble-server.ini -supw 'password'
```

The Ice secret (`prmurmurpassword` in `data/mumble-server.ini` and
`data/mumo/mumo.ini`) may stay as it is: Ice listens on 127.0.0.1 only. If
you change it, use the same value in both files and run
`sudo docker compose restart`.

Updating the code without losing channels (the build takes 10–20 minutes
while the server keeps running; downtime only for the restart):

```bash
git pull
sudo docker compose build && sudo docker compose up -d
sudo docker logs prmurmur15 2>&1 | grep -E "running on|ServerCallback" | tail -2
```

Expect `Murmur 1.5.857 running on ...` and `Added Ice ServerCallback`.

Start over (new channels): `sudo docker compose down && sudo mv data
data.old`, then the first installation again.

Notes:
- the container hands `/data` to the `mumble-server` user (uid 101); edit
  files in `data/` from the host with `sudo`;
- the Ice port in `data/mumble-server.ini` and `data/mumo/mumo.ini` must
  match, otherwise mumo logs `Server refused connection` and the container
  keeps restarting;
- all state is in `data/`: database, configs, logs — that is the backup.

## 8. Windows

Archive `PRMumble-Server-1.5.857-win64.zip`: the same server with the PR
patch, embedded Python 3.11 with Ice, mumo with prbf2, scripts and `.bat`
files (`start`, `stop`, `setup-channels`, `grant-bot`, `check-acl`,
`set-superuser-password`). Nothing to install. The guide is inside:
`README_EN.txt` and `README_RU.txt`.

Download: [Releases](../../releases) (`PRMumble-Server-1.5.857-win64.zip`).
Build yourself: Actions → `windows-build` → Run workflow; the archive is the
run's artifact. It uses the prebuilt environment of the Mumble project (vcpkg
`x64-windows-static-md`, MSVC). The build tests the package itself: server,
Ice, channel creation, mumo with prbf2. Package sources: `windows/package/`.
The scripts take their paths from `PRMUMBLE_*` variables; without them they
use the Docker paths.

## 9. Diagnostics

| Command | Shows |
|---|---|
| `sudo docker exec prmurmur15 python3 /opt/scripts/check_acl.py <nick>` | a player's permissions in every channel |
| `sudo docker exec prmurmur15 python3 /opt/scripts/voice_probe.py 60` | a bot listens to the busiest squad: talk type and whether voice carries a position (needs `pymumble`) |
| `sudo tail -n 50 data/logs/mumo.log` | what mumo does (`level = 10` in `mumo.ini` for detail) |
| `python scripts/hud_dump.py` (on the game PC) | what PRMumble hands the launcher HUD: name, channel, talk state, position |

## 10. Project layout

| File | What |
|---|---|
| `mumble-server.Dockerfile` | builds Mumble 1.5.857 with the PR patch, mumo, Ubuntu 24.04 |
| `docker-compose.yaml` | service `prmurmur15` |
| `config/mumble-server.ini`, `config/mumo.ini` | config templates (64740, Ice 6504) |
| `config/games.txt` | example list of game servers |
| `mumo/modules/prbf2.py` | PR logic in Python 3 |
| `docs/patch_identity.py` | server patch: identity and position for the HUD |
| `docs/port_prbf2.py` | reproducible Python 3 port of prbf2.py |
| `scripts/initialsetup.sh` | first installation on an empty `data/` |
| `scripts/createchannel.sh` | creates the channels on the running server |
| `scripts/setup_channels.py` | channel tree, ACL and mumo map (Ice) |
| `scripts/check_acl.py` | effective permissions of connected players |
| `scripts/grant_bot.py` | bot rights: enter, listen, speak everywhere |
| `scripts/link_teams.py` | cross-team local voice on/off |
| `scripts/voice_probe.py` | what the server relays in voice packets |
| `scripts/hud_dump.py` | what PRMumble gives the HUD (Windows, game PC) |
| `scripts/entrypoint.sh` | starts server and mumo in the container |
| `windows/package/` | Windows package files: configs, `.bat`, `games.txt`, guides |
| `.github/workflows/windows-build.yml` | Windows package build on GitHub Actions |
