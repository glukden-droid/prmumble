PROJECT REALITY MUMBLE SERVER FOR WINDOWS
Mumble 1.5.857 + PR patch + mumo/prbf2
=========================================

Contents
  1. What this is
  2. Requirements
  3. What is in the folder
  4. Installation (first start)
  5. Pointing the game server and players to it
  6. Firewall
  7. Running it as a Windows service
  8. Administrators
  9. Bots (recorder, music, relay)
 10. Day-to-day operation
 11. Updating, backup, moving to another machine
 12. Troubleshooting
 13. Technical notes


1. WHAT THIS IS
---------------
A ready-to-run voice server for Project Reality: BF2 game servers.

  - mumble-server.exe : Mumble server 1.5.857 built from the official
    sources with a small Project Reality patch. The patch makes it behave
    like the old PRMurmur 1.2 for the PR client, so the in-game HUD shows
    who is talking (see 13).
  - mumo + prbf2 : a helper that moves every player into the channel of
    his team and squad, based on what the PR client reports. Players do
    not pick channels themselves.

One Mumble server can serve several game servers; each gets its own set
of team and squad channels.


2. REQUIREMENTS
---------------
  - Windows 10 / 11 or Windows Server 2016 or newer, 64-bit.
  - About 200 MB of disk space.
  - Nothing to install: Python and all libraries are inside the folder.
  - Port 64740 TCP+UDP reachable from the players (see 6).
  - Players use the Mumble client that ships with Project Reality
    (PRMumble, Mumble 1.3.0). It is started by the PR launcher.


3. WHAT IS IN THE FOLDER
------------------------
  mumble-server.exe            the voice server
  mumble-server.ini            server settings (port, welcome text, ...)
  MumbleServer.ice             interface file used by mumo and the scripts
  games.txt                    YOUR game servers - edit this first
  start.bat                    starts the server, then mumo
  stop.bat                     stops both
  setup-channels.bat           creates all channels (once, on first start)
  set-superuser-password.bat   sets the SuperUser (owner) password
  grant-bot.bat                gives a bot rights in every channel
  check-acl.bat                shows what a connected player may do
  python\                      embedded Python 3.11 with ZeroC Ice
  mumo\                        mumo, its config mumo.ini, module prbf2
  scripts\                     the Python scripts behind the .bat files
  README_EN.txt / README_RU.txt   this guide in English and Russian

Created while running:
  murmur.sqlite                the database: channels, users, bans
  mumble-server.log            server log
  mumo\mumo.log                mumo log
  mumo\modules-enabled\prbf2.ini   channel map written by setup-channels


4. INSTALLATION (FIRST START)
-----------------------------
Unpack the folder to a permanent place. A short path is easiest to work
with, e.g.  C:\PRMumble

Step 1 - list your game servers in games.txt
  One line per game server:

      name | channel title | ip:port

  name           short id, latin letters and digits, unique: main0, main1
  channel title  what players see in Mumble: [EU] My PR Server #1
  ip:port        the address players use to join the GAME server (the game
                 port, e.g. 16567). Several addresses for the same server
                 (public and LAN IP) are separated by commas.

  Example:
      main0 | [EU] My PR Server #1 | 203.0.113.10:16567
      main1 | [EU] My PR Server #2 | 203.0.113.10:16568

  The ip:port must match exactly what the PR client reports, otherwise
  players are not moved. If unsure, see "Players are not moved" in 12.

  Save games.txt as UTF-8 if the titles contain non-latin letters.

Step 2 - start the server
  Run start.bat. The server starts (a Mumble icon appears in the tray) and
  creates an empty database. The window then says there is no channel map
  yet and stops - that is expected on the first start.

Step 3 - create the channels
  With the server still running, run setup-channels.bat. It creates:

      Root
        Lobby                       where players land on connect
        PR BF2 Game Servers
          <channel title>           one per line of games.txt
            Team 1                  (opfor)
              Commander, No Squad, Squad 1 ... Squad 9
            Team 2                  (blufor)
              Commander, No Squad, Squad 1 ... Squad 9

  and writes mumo\modules-enabled\prbf2.ini (the channel map for mumo).
  It refuses to run on a server that already has channels.

Step 4 - start everything
  Close the start.bat window, run stop.bat, then run start.bat again.
  Now mumo starts too and keeps running in that window.

Step 5 - set the SuperUser password
      set-superuser-password.bat YourStrongPassword
  SuperUser is the owner account (see 8).

Step 6 - change the Ice secret (recommended)
  The Ice secret protects the local admin interface mumo uses. Pick a
  random string and put the SAME value in:
      mumble-server.ini   icesecretread= and icesecretwrite=
      mumo\mumo.ini       secret =
  Then stop.bat and start.bat.

Step 7 - test
  Start Project Reality, join one of your game servers, open the PR Mumble
  window. You should be moved into your team/squad channel within a few
  seconds, and squad mates should hear you.


5. POINTING THE GAME SERVER AND PLAYERS TO IT
---------------------------------------------
Players' PR clients must connect to this Mumble server: address of this
machine, port 64740 - the same way as with your previous Mumble server.

If you run a different port, change port= in mumble-server.ini.

realityconfig_admin.py on the game server: mum_mumbleSecret can stay as
it is. The PR identity password check is switched off on this server
(prbf2.ini has an empty secret) because the PR client does not relay a
matching password; the old PRMurmur did not verify it successfully either.


6. FIREWALL
-----------
Open for incoming traffic:
      64740 TCP and 64740 UDP      (voice and control)

Do NOT open 6504. That is the Ice admin interface; it listens on
127.0.0.1 only and must stay local.

PowerShell (as Administrator):
  New-NetFirewallRule -DisplayName "PR Mumble TCP" -Direction Inbound -Protocol TCP -LocalPort 64740 -Action Allow
  New-NetFirewallRule -DisplayName "PR Mumble UDP" -Direction Inbound -Protocol UDP -LocalPort 64740 -Action Allow

If the machine is behind a router or a hosting firewall, forward / allow
the same port there.


7. RUNNING IT AS A WINDOWS SERVICE
----------------------------------
start.bat runs in a console window and stops when you log off. For a
server that survives reboots and logoffs use one of these:

Option A - NSSM (recommended), https://nssm.cc
  nssm install PRMumble "C:\PRMumble\start.bat"
  nssm set PRMumble AppDirectory "C:\PRMumble"
  nssm set PRMumble AppExit Default Restart
  nssm start PRMumble
  Stop:   nssm stop PRMumble   (then run stop.bat to be sure the server
          process is gone)

Option B - Task Scheduler
  Create Task:
    General:  "Run whether user is logged on or not", "Run with highest
              privileges"
    Triggers: At startup
    Actions:  Start a program: C:\PRMumble\start.bat
              Start in:        C:\PRMumble
    Settings: untick "Stop the task if it runs longer than ..."

In both cases mumo stops if the server dies and start.bat ends; NSSM
restarts it automatically.


8. ADMINISTRATORS
-----------------
SuperUser
  The owner account. Connect with any Mumble client (1.4+ recommended for
  administration) using user name  SuperUser  and the password from step 5.
  SuperUser can do everything; use it for administration only and give
  day-to-day admins their own accounts (below).

Adding admins
  1. The future admin connects once with his own Mumble client and
     registers himself (right click on own name -> Register).
  2. As SuperUser: right click on Root -> Edit -> Groups -> group "admin"
     -> add the registered user -> OK.
  Members of "admin" have full rights everywhere (Write on Root): move and
  mute players, edit channels, listen to any channel.

Banning, kicking, moving: right click on a player in the client.


9. BOTS (RECORDER, MUSIC, RELAY)
--------------------------------
Ordinary players cannot enter or listen to team and squad channels. A bot
that must do that is put into the group "bots":

  1. Make the bot connect WITH a client certificate (any self-signed
     certificate; create one with
       openssl req -x509 -newkey rsa:2048 -nodes -keyout bot.key -out bot.crt -days 3650 -subj "/CN=MyBot"
     and point the bot's settings to bot.crt / bot.key).
  2. While the bot is connected:
       grant-bot.bat MyBot
     This registers the bot under its certificate and adds it to "bots".
  3. Reconnect the bot.

Bots may then enter every channel, listen (Mumble 1.4+ "listen to
channel"), speak, whisper, write text and mute/deafen others. mumo leaves
bots alone because they have no PR game context.


10. DAY-TO-DAY OPERATION
------------------------
  Start:            start.bat  (or the service)
  Stop:             stop.bat   (or stop the service)
  Who may do what:  check-acl.bat PartOfNick
  Logs:             mumble-server.log, mumo\mumo.log
  More mumo detail: in mumo\mumo.ini set  level = 10  (every move is
                    logged), restart mumo; set back to 30 afterwards, the
                    log grows fast on a full server.

Normal log lines that are NOT errors:
  "<player> not allowed to Enter in Squad N"
      The PR client tries to join its squad itself; the server refuses
      and mumo moves the player a moment later.
  "Zeroconf ..."           harmless.

Adding a game server later: setup-channels.bat only works on an empty
server. Either start over (see 11, "Start over") or create the channels
with an admin client and add a [gN] section to prbf2.ini by hand
(copy an existing one and change the channel ids, name and ipport_filter).


11. UPDATING, BACKUP, MOVING TO ANOTHER MACHINE
-----------------------------------------------
Backup
  Stop the server, copy:
      murmur.sqlite, mumble-server.ini, games.txt,
      mumo\mumo.ini, mumo\modules-enabled\prbf2.ini
  The database holds channels, registered users, admins and bans.

Updating to a new package
  stop.bat, unpack the new package into a NEW folder, copy the five files
  above into it, start.bat. Do not run setup-channels.bat - the channels
  are already in murmur.sqlite.

Moving to another machine
  Same as updating. Players keep their registrations; they may see a
  certificate warning once if you do not copy murmur.sqlite (the server
  certificate is stored in it).

Start over (new channels)
  stop.bat, delete murmur.sqlite and mumo\modules-enabled\prbf2.ini,
  then follow section 4 from step 2. Registrations, admins and bans are
  lost; bots must be granted again.


12. TROUBLESHOOTING
-------------------
start.bat: "The server did not open its Ice port"
  - Look at mumble-server.log.
  - Another program uses port 64740 or 6504 (e.g. an old Murmur):
      netstat -ano | findstr "64740 6504"
  - The ini has a typo; the server writes the reason into the log.

mumo window closes / mumo.log says "Server refused connection"
  The Ice port or secret in mumo\mumo.ini does not match
  mumble-server.ini (ice= line and icesecret*). Make them equal.

Players are not moved into squad channels
  1. Set level = 10 in mumo\mumo.ini, restart, let a player join, then
     look at mumo\mumo.log.
  2. A line "No matching game found" or nothing after the player's
     context line: the ip:port the client reports differs from games.txt
     / ipport_filter in prbf2.ini. The context line shows a base64 string;
     decode it (e.g. in PowerShell:
       [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("<text>"))
     ) - it contains {"ipport":"x.x.x.x:port"}. Put exactly that into
     ipport_filter of the matching [gN] section in prbf2.ini (several
     values separated by commas) and restart mumo.
  3. "Failed verifying identity": prbf2.ini has a non-empty secret. Set
     "secret =" (empty) and restart mumo.

Players cannot talk / microphone shows as muted by the server
  - A player in the game server channel (above Team 1/2) cannot talk:
    that is where mumo puts players that left the game.
  - Make sure prbf2.ini has an empty secret (see above).
  - Reconnecting the PR Mumble client refreshes what it shows.

The HUD does not show who is talking
  - Make sure you run THIS mumble-server.exe (the stock Mumble server
    lacks the PR patch). mumble-server.log starts with
    "Murmur 1.5.857 running on ...".
  - For local (proximity) voice the HUD shows only players within about
    70 m - that is the PR launcher's rule.

Privacy warning about channel listeners in the PR client
  Expected: listeners are enabled for bots and admins. To switch the
  warning off (and listeners with it) set listenersperchannel=0 and
  listenersperuser=0 in mumble-server.ini and restart.


13. TECHNICAL NOTES
-------------------
PR patch (applied to the Mumble 1.5.857 sources):
  - plugin identity of every player is sent to the other clients, also in
    the user list a client receives on connect (stock Mumble keeps it
    server-side). The PR client takes the in-game name for the HUD from it.
  - UserState field 20 is "repeated float position", as in PRMurmur; the
    PR client sends its in-game position there and the server relays it -
    unlike PRMurmur only to the sender's own and linked channels (his team),
    so enemies never receive it (no radar for modified clients).
    Stock 1.5 uses field 20 for temporary_access_tokens; they are moved to
    field 120 (PR clients never send them).
  - The plugin context (game server address) is still never sent to other
    clients, as in PRMurmur.

mumo/prbf2 (Python 3 port of the PR module) also works around a Mumble 1.5
issue where group changes made the server tell clients a player was
muted: groups are only changed when team/squad/role really change, and the
correct "suppressed" state is sent after every move.

Ice: 127.0.0.1:6504, used by mumo and the scripts. Server 1.5.857, Python
3.11, ZeroC Ice 3.7.
