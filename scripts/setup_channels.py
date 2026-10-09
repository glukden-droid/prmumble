#!/usr/bin/env python3
# Builds the PR channel tree from scratch on an EMPTY server over Ice and
# writes the matching mumo channel map (prbf2.ini).
#
# Run inside the container while the server is up:
#   python3 /opt/scripts/setup_channels.py [--force]
#
# Tree:  Root
#          Lobby
#          PR BF2 Game Servers
#            <game name>                  one per GAMES entry
#              Team 1 (opfor)  Commander, No Squad, Squad 1..9
#              Team 2 (blufor) Commander, No Squad, Squad 1..9
#
# Players cannot enter game channels themselves; mumo moves them by the
# team/squad the PR client reports. ACLs follow the old PRMurmur server.

import os
import sys
import configparser
import Ice

# Paths default to the Docker image; the Windows package sets them via the
# environment (see windows/package/*.bat).
SLICE = os.environ.get("PRMUMBLE_SLICE", "/usr/share/MumbleServer.ice")
MUMO_INI = os.environ.get("PRMUMBLE_MUMO_INI", "/data/mumo/mumo.ini")
OUT = os.environ.get("PRMUMBLE_PRBF2_INI", "/data/mumo/modules-enabled/prbf2.ini")
# Optional list of game servers, one per line: name|channel title|ip:port
# (several ip:port separated by commas). Replaces GAMES below when given.
GAMES_FILE = os.environ.get("PRMUMBLE_GAMES", "")
SERVER_ID = 1
# Identity check shared with mum_mumbleSecret on the game servers. Empty =
# off: the passwords the PR client relays never matched
# (checked 2026-10-02), so it stays off until that is understood.
SECRET = ""

# (mumo game name, channel title, game server ip:port)
GAMES = [
    ("main0", "[EU] My PR Server #1", "203.0.113.10:16567"),
]

SQUADS = ["no", "first", "second", "third", "fourth", "fifth",
          "sixth", "seventh", "eighth", "ninth"]

# Permission bits (MumbleServer.ice)
WRITE, TRAVERSE, ENTER, SPEAK = 0x1, 0x2, 0x4, 0x8
MUTEDEAFEN, MOVE, MAKECHANNEL = 0x10, 0x20, 0x40
WHISPER, TEXT, MAKETEMP, LISTEN = 0x100, 0x200, 0x400, 0x800
REGISTER, SELFREGISTER = 0x40000, 0x80000
BOT_ALLOW = TRAVERSE | ENTER | SPEAK | MUTEDEAFEN | WHISPER | TEXT | LISTEN


def rules(M, kind, gname=None, squad=None, games=()):
    """ACL entries and group definitions of one channel kind.

    Shared with scripts/reset_acl.py, so a reset gives exactly the rights a
    fresh setup gives. kind: root, lobby, game, team, commander, squad.
    """
    def acl(group, allow=0, deny=0, here=True, sub=True):
        return M.ACL(applyHere=here, applySubs=sub, inherited=False,
                     userid=-1, group=group, allow=allow, deny=deny)

    def group(name):
        return M.Group(name=name, inherited=False, inherit=True,
                       inheritable=True, add=[], remove=[], members=[])

    if kind == "root":
        # admins manage everything; nobody talks in Root itself,
        # self-registration is off
        return ([acl("admin", allow=WRITE),
                 acl("admin", allow=REGISTER),
                 acl("all", deny=SPEAK | WHISPER, sub=False),
                 acl("all", deny=SPEAK | WHISPER | SELFREGISTER),
                 acl("bots", allow=BOT_ALLOW)],
                [group("admin"), group("bots"), group("bf2_linked")]
                + [group("bf2_%s_game" % g) for g in games])
    if kind == "lobby":
        # as in PRMurmur: nobody talks in the Lobby (text chat is fine);
        # only bots and admins may speak there
        return ([acl("all", deny=SPEAK | WHISPER),
                 acl("admin", allow=SPEAK | WHISPER | TEXT),
                 acl("bots", allow=BOT_ALLOW)], [])
    if kind == "game":
        return ([acl("~bf2_%s_admin" % gname,
                     allow=MAKECHANNEL | MOVE | MUTEDEAFEN | TRAVERSE),
                 acl("all", deny=SPEAK | WHISPER, sub=False),
                 acl("bots", allow=BOT_ALLOW, sub=False)], [])
    if kind == "team":
        return ([
            # nobody enters, talks or listens unless mumo put them here
            acl("all", deny=TRAVERSE | ENTER | SPEAK | MAKECHANNEL
                | WHISPER | TEXT | LISTEN | MAKETEMP),
            acl("~bf2_%s_game" % gname, allow=SPEAK | TEXT),
            acl("~bf2_%s_game" % gname, allow=TRAVERSE | WHISPER, sub=False),
            acl("~bf2_team", allow=TRAVERSE | WHISPER, sub=False),
            acl("~bf2_%s_admin" % gname, allow=MOVE | MUTEDEAFEN | TRAVERSE),
            # bots (scripts/grant_bot.py) may enter, listen and speak
            acl("bots", allow=BOT_ALLOW),
        ], [group("bf2_team"), group("bf2_commander"), group("bf2_squad_leader")]
           + [group("bf2_%s_squad" % s) for s in SQUADS]
           + [group("bf2_%s_squad_leader" % s) for s in SQUADS])
    if kind == "commander":
        return ([acl("~bf2_commander", allow=TRAVERSE | WHISPER, sub=False),
                 acl("~bf2_squad_leader", allow=WHISPER, sub=False)], [])
    if kind == "squad":
        return ([acl("~bf2_%s_squad" % squad, allow=TRAVERSE | WHISPER, sub=False),
                 acl("~bf2_commander", allow=TRAVERSE | WHISPER, sub=False),
                 acl("~bf2_squad_leader", allow=WHISPER, sub=False)], [])
    raise ValueError(kind)


def main():
    force = "--force" in sys.argv
    global GAMES
    if GAMES_FILE:
        GAMES = []
        with open(GAMES_FILE, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) != 3:
                    sys.exit("setup: bad line in %s: %r" % (GAMES_FILE, line))
                GAMES.append(tuple(parts))
        if not GAMES:
            sys.exit("setup: no game servers in %s" % GAMES_FILE)
    cfg = configparser.ConfigParser()
    cfg.read(MUMO_INI)
    host, port = cfg["ice"]["host"], cfg["ice"]["port"]
    secret = cfg["ice"]["secret"]

    Ice.loadSlice("", ["-I" + Ice.getSliceDir(), SLICE])
    import MumbleServer as M

    props = Ice.createProperties()
    props.setProperty("Ice.ImplicitContext", "Shared")
    props.setProperty("Ice.Default.EncodingVersion", "1.0")
    init = Ice.InitializationData()
    init.properties = props
    ic = Ice.initialize(init)
    ic.getImplicitContext().put("secret", secret)
    meta = M.MetaPrx.checkedCast(
        ic.stringToProxy("Meta:tcp -h %s -p %s" % (host, port)))
    srv = meta.getServer(SERVER_ID)

    existing = srv.getChannels()
    if len(existing) > 1 and not force:
        sys.exit("setup: server already has %d channels; use an empty "
                 "database or pass --force to add anyway" % len(existing))

    srv.setACL(0, *rules(M, "root", games=[g[0] for g in GAMES]), True)

    lobby = srv.addChannel("Lobby", 0)
    srv.setACL(lobby, *rules(M, "lobby"), True)
    games_root = srv.addChannel("PR BF2 Game Servers", 0)

    ini = configparser.ConfigParser()
    ini["prbf2"] = {"gamecount": str(len(GAMES)), "secret": SECRET}

    for i, (gname, title, ipport) in enumerate(GAMES):
        gsec = {"name": gname, "mumble_server": str(SERVER_ID),
                "ipport_filter": ipport}
        gch = srv.addChannel(title, games_root)
        # base stays 0 (Root) as with prbf2man.py: mumo keeps the
        # bf2_<game>_game group there
        gsec["base"] = "0"
        gsec["left"] = str(gch)
        srv.setACL(gch, *rules(M, "game", gname), True)

        for team, tname in (("opfor", "Team 1"), ("blufor", "Team 2")):
            tch = srv.addChannel(tname, gch)
            gsec[team] = str(tch)
            srv.setACL(tch, *rules(M, "team", gname), True)

            cch = srv.addChannel("Commander", tch)
            gsec["%s_commander" % team] = str(cch)
            srv.setACL(cch, *rules(M, "commander"), True)
            cstate = srv.getChannelState(cch)
            cstate.position = -1          # Commander on top
            srv.setChannelState(cstate)
            links = [cch]

            for n, s in enumerate(SQUADS):
                sch = srv.addChannel("No Squad" if n == 0 else "Squad %d" % n,
                                     tch)
                gsec["%s_%s_squad" % (team, s)] = str(sch)
                gsec["%s_%s_squad_leader" % (team, s)] = str(sch)
                srv.setACL(sch, *rules(M, "squad", squad=s), True)
                links.append(sch)

            # The team channel is linked to its Commander and squad channels
            # (prbf2man.py), so whispers to linked channels reach them.
            tstate = srv.getChannelState(tch)
            tstate.links = links
            srv.setChannelState(tstate)

        ini["g%d" % i] = gsec
        print("setup: %s -> channel %d (%s)" % (gname, gch, ipport))

    with open(OUT, "w") as f:
        ini.write(f)
    print("setup: %d channels, map written to %s"
          % (len(srv.getChannels()), OUT))
    print("setup: restart the container so mumo reloads the map")
    ic.destroy()


if __name__ == "__main__":
    main()
