#!/usr/bin/env python3
# Prints the effective permissions of connected users in every channel, and
# the temporary bf2_* group memberships mumo gave them.
#
#   docker exec prmurmur15 python3 /opt/scripts/check_acl.py [name-part]

import os
import sys
import configparser
import Ice

SLICE = os.environ.get("PRMUMBLE_SLICE", "/usr/share/MumbleServer.ice")
MUMO_INI = os.environ.get("PRMUMBLE_MUMO_INI", "/data/mumo/mumo.ini")

BITS = [("Write", 0x1), ("Traverse", 0x2), ("Enter", 0x4), ("Speak", 0x8),
        ("Whisper", 0x100), ("Text", 0x200), ("Listen", 0x800),
        ("Move", 0x20), ("MakeChannel", 0x40)]


def main():
    want = sys.argv[1].lower() if len(sys.argv) > 1 else ""
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
    meta = M.MetaPrx.checkedCast(ic.stringToProxy(
        "Meta:tcp -h %s -p %s" % (cfg["ice"]["host"], cfg["ice"]["port"])))
    srv = meta.getServer(1)

    chans = srv.getChannels()

    def path(cid):
        parts = []
        while cid in chans and cid != 0:
            parts.append(chans[cid].name)
            cid = chans[cid].parent
        return "/".join(reversed(parts)) or "Root"

    for sess, u in srv.getUsers().items():
        if want and want not in u.name.lower():
            continue
        print("== %s session %d userid %d in [%d] %s"
              % (u.name, sess, u.userid, u.channel, path(u.channel)))
        # temporary groups mumo added (look on every channel that has groups)
        for cid in sorted(chans):
            _, groups, _ = srv.getACL(cid)
            for g in groups:
                if sess in g.members or sess in g.add:
                    print("   group %-28s on [%d] %s" % (g.name, cid, path(cid)))
        for cid in sorted(chans):
            perms = [n for n, b in BITS if srv.hasPermission(sess, cid, b)]
            print("   [%3d] %-55s %s" % (cid, path(cid)[:55], " ".join(perms)))
    ic.destroy()


if __name__ == "__main__":
    main()
