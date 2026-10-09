#!/usr/bin/env python3
# Switches cross-team local voice on or off: links Team 1 and Team 2 of a
# game server, so normal (local) speech also reaches the enemy team. The PR
# client fades it with distance (positional audio), so only enemies nearby
# hear it. Squad radio and commander channels are not affected. Player
# positions for the HUD still go to the own team only (server patch).
#
#   link_teams.py status
#   link_teams.py on  [game ...]     game = mumo name from prbf2.ini (main0)
#   link_teams.py off [game ...]     no game = every game server
#
# Docker:  docker exec prmurmur15 python3 /opt/scripts/link_teams.py on main0
# Windows: link-teams.bat on main0
# The links live in the database and survive restarts.

import os
import sys
import configparser
import Ice

SLICE = os.environ.get("PRMUMBLE_SLICE", "/usr/share/MumbleServer.ice")
MUMO_INI = os.environ.get("PRMUMBLE_MUMO_INI", "/data/mumo/mumo.ini")
PRBF2_INI = os.environ.get("PRMUMBLE_PRBF2_INI", "/data/mumo/modules-enabled/prbf2.ini")
SERVER_ID = 1


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("on", "off", "status"):
        sys.exit("usage: link_teams.py status | on [game ...] | off [game ...]")
    action, wanted = sys.argv[1], sys.argv[2:]

    games = configparser.ConfigParser()
    games.read(PRBF2_INI, encoding="utf-8")
    sections = [s for s in games.sections() if s != "prbf2" and games.has_option(s, "opfor")]
    if not sections:
        sys.exit("link_teams: no game servers in %s" % PRBF2_INI)
    names = {games.get(s, "name", fallback=s): s for s in sections}
    unknown = [g for g in wanted if g not in names]
    if unknown:
        sys.exit("link_teams: unknown game(s) %s; known: %s" % (", ".join(unknown), ", ".join(names)))
    selected = [names[g] for g in wanted] if wanted else sections

    cfg = configparser.ConfigParser()
    cfg.read(MUMO_INI)
    Ice.loadSlice("", ["-I" + Ice.getSliceDir(), SLICE])
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

    for s in selected:
        name = games.get(s, "name", fallback=s)
        t1, t2 = games.getint(s, "opfor"), games.getint(s, "blufor")
        if t1 not in chans or t2 not in chans:
            print("%-8s team channels %d/%d not found, skipped" % (name, t1, t2))
            continue
        title = chans[chans[t1].parent].name if chans[t1].parent in chans else "?"

        # every channel of each team subtree (team, commander, squads, ...)
        def subtree(root):
            out, todo = set(), [root]
            while todo:
                c = todo.pop()
                out.add(c)
                todo += [x for x, ch in chans.items() if ch.parent == c]
            return out
        side1, side2 = subtree(t1), subtree(t2)

        # any link from Team 1's side to Team 2's side counts - also the
        # manual ones set in a client (e.g. Team 2 <-> Team 1/Squad 1, as on
        # the old PRMurmur), not only Team 1 <-> Team 2
        def cross_links():
            found = []
            for c in side1:
                for l in srv.getChannelState(c).links:
                    if l in side2:
                        found.append((c, l))
            return found

        found = cross_links()
        if action == "off":
            for c, _ in found:
                st = srv.getChannelState(c)
                st.links = [l for l in st.links if l not in side2]
                srv.setChannelState(st)
            found = cross_links()
        elif action == "on" and not found:
            st = srv.getChannelState(t1)
            st.links = list(st.links) + [t2]
            srv.setChannelState(st)
            found = cross_links()

        def label(c, team, tname):
            return tname if c == team else "%s/%s" % (tname, chans[c].name)
        detail = ", ".join("%s <-> %s" % (label(a, t1, chans[t1].name), label(b, t2, chans[t2].name))
                           for a, b in found)
        print("%-8s %-40s cross-team local voice: %s%s" % (
            name, title[:40], "ON" if found else "off", "  (" + detail + ")" if found else ""))
    ic.destroy()


if __name__ == "__main__":
    main()
