#!/usr/bin/env python3
# Puts the rights (ACL) of the existing PR channel tree back to exactly what
# setup_channels.py sets on a fresh server - without recreating channels, so
# registrations, admins, bans and bot registrations stay. Also resets the
# team links (Team <-> its Commander and squads only; cross-team voice off).
#
# Members of the root groups (admin, bots, ...) are kept. Temporary groups
# mumo gives to players are lost by a reset, so mumo must be restarted
# afterwards (restart the container / start.bat) - it then gives them again.
#
#   docker exec prmurmur15 python3 /opt/scripts/reset_acl.py [--dry-run]
#   docker restart prmurmur15

import os
import sys
import configparser
import Ice

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_channels as sc  # noqa: E402  (shared rules)

PRBF2_INI = os.environ.get("PRMUMBLE_PRBF2_INI", "/data/mumo/modules-enabled/prbf2.ini")
SERVER_ID = 1


def main():
    dry = "--dry-run" in sys.argv
    games = configparser.ConfigParser()
    games.read(PRBF2_INI, encoding="utf-8")
    sections = [s for s in games.sections() if s != "prbf2" and games.has_option(s, "opfor")]
    if not sections:
        sys.exit("reset_acl: no game servers in %s" % PRBF2_INI)

    cfg = configparser.ConfigParser()
    cfg.read(sc.MUMO_INI)
    Ice.loadSlice("", ["-I" + Ice.getSliceDir(), sc.SLICE])
    import MumbleServer as M
    props = Ice.createProperties()
    props.setProperty("Ice.ImplicitContext", "Shared")
    props.setProperty("Ice.Default.EncodingVersion", "1.0")
    init = Ice.InitializationData()
    init.properties = props
    ic = Ice.initialize(init)
    ic.getImplicitContext().put("secret", cfg["ice"]["secret"])
    srv = M.MetaPrx.checkedCast(ic.stringToProxy(
        "Meta:tcp -h %s -p %s" % (cfg["ice"]["host"], cfg["ice"]["port"]))).getServer(SERVER_ID)
    chans = srv.getChannels()
    done = []

    def apply(cid, acls_groups, label):
        acls, groups = acls_groups
        done.append(label)
        if not dry:
            srv.setACL(cid, acls, groups, True)

    # Root: keep the members of existing root groups (admin, bots, ...)
    names = [games.get(s, "name") for s in sections]
    acls, groups = sc.rules(M, "root", games=names)
    _, old_groups, _ = srv.getACL(0)
    old = {g.name: g for g in old_groups if not g.inherited}
    for g in groups:
        if g.name in old:
            g.add = list(old[g.name].add)
            g.remove = list(old[g.name].remove)
    for name, g in old.items():          # groups the template does not know
        if name not in {x.name for x in groups}:
            groups.append(g)
    apply(0, (acls, groups), "Root")

    for cid, ch in chans.items():
        if ch.parent == 0 and ch.name == "Lobby":
            apply(cid, sc.rules(M, "lobby"), "Lobby")

    for s in sections:
        sec = games[s]
        gname = sec.get("name")
        t1, t2 = sec.getint("opfor"), sec.getint("blufor")
        if t1 not in chans or t2 not in chans:
            print("reset_acl: %s: team channels %d/%d missing, skipped" % (gname, t1, t2))
            continue
        apply(chans[t1].parent, sc.rules(M, "game", gname), "%s game" % gname)
        for team, tch in (("opfor", t1), ("blufor", t2)):
            apply(tch, sc.rules(M, "team", gname), "%s %s" % (gname, team))
            links = []
            cch = sec.getint("%s_commander" % team)
            if cch in chans:
                apply(cch, sc.rules(M, "commander"), "%s %s commander" % (gname, team))
                links.append(cch)
            for sq in sc.SQUADS:
                key = "%s_%s_squad" % (team, sq)
                if key in sec and sec.getint(key) in chans:
                    sch = sec.getint(key)
                    apply(sch, sc.rules(M, "squad", squad=sq), "%s %s %s" % (gname, team, sq))
                    links.append(sch)
            if not dry:
                st = srv.getChannelState(tch)
                st.links = links
                srv.setChannelState(st)

    print("reset_acl: %s %d channels%s" % ("would reset" if dry else "reset", len(done),
          " (dry run)" if dry else ""))
    if not dry:
        print("reset_acl: team links reset (cross-team voice off); now restart mumo "
              "(docker restart prmurmur15 / start.bat) so players get their groups back")
    ic.destroy()


if __name__ == "__main__":
    main()
