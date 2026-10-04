#!/usr/bin/env python3
# Gives a bot (recorder, music, relay...) the right to enter, listen to,
# speak and mute/deafen others in every channel, including the team and squad
# channels that are closed to everyone else.
#
#   docker exec prmurmur15 python3 /opt/scripts/grant_bot.py <bot name>
#
# The bot must be connected with a client certificate the first time: the
# script registers it under that certificate, then puts the registered user
# into the root group "bots". The group gets an ACL entry on Root and on every
# team channel (after the "all deny" entry there, otherwise the deny wins).
# Running it again is harmless; a second bot is added to the same group.

import hashlib
import os
import sys
import configparser
import Ice

SLICE = os.environ.get("PRMUMBLE_SLICE", "/usr/share/MumbleServer.ice")
MUMO_INI = os.environ.get("PRMUMBLE_MUMO_INI", "/data/mumo/mumo.ini")
SERVER_ID = 1
GROUP = "bots"

TRAVERSE, ENTER, SPEAK, MUTEDEAFEN, WHISPER, TEXT, LISTEN = 0x2, 0x4, 0x8, 0x10, 0x100, 0x200, 0x800
BOT_ALLOW = TRAVERSE | ENTER | SPEAK | MUTEDEAFEN | WHISPER | TEXT | LISTEN


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: grant_bot.py <bot name>")
    name = sys.argv[1]

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

    # 1. registered user id (register by certificate if needed)
    uid = next((i for i, n in srv.getRegisteredUsers(name).items() if n == name), None)
    if uid is None:
        online = [u for u in srv.getUsers().values() if u.name == name]
        if not online:
            sys.exit("grant_bot: '%s' is neither registered nor connected" % name)
        certs = srv.getCertificateList(online[0].session)
        if not certs:
            sys.exit("grant_bot: '%s' has no client certificate, cannot register" % name)
        cert_hash = hashlib.sha1(bytes(certs[0])).hexdigest()
        uid = srv.registerUser({M.UserInfo.UserName: name, M.UserInfo.UserHash: cert_hash})
        print("grant_bot: registered '%s' as user %d" % (name, uid))
        # the registration applies to the session after a reconnect
    else:
        print("grant_bot: '%s' is registered as user %d" % (name, uid))

    def own(acls, groups):
        return [a for a in acls if not a.inherited], [g for g in groups if not g.inherited]

    def acl(group):
        return M.ACL(applyHere=True, applySubs=True, inherited=False,
                     userid=-1, group=group, allow=BOT_ALLOW, deny=0)

    def upsert(acls):
        # widen an existing bots entry to the current BOT_ALLOW
        found = False
        for a in acls:
            if a.group == GROUP:
                a.allow |= BOT_ALLOW
                found = True
        return found

    # 2. root: group "bots" with the user, and the allow entry
    acls, groups, inherit = srv.getACL(0)
    acls, groups = own(acls, groups)
    g = next((x for x in groups if x.name == GROUP), None)
    if g is None:
        g = M.Group(name=GROUP, inherited=False, inherit=True, inheritable=True,
                    add=[], remove=[], members=[])
        groups.append(g)
    if uid not in g.add:
        g.add = list(g.add) + [uid]
    if not upsert(acls):
        acls.append(acl(GROUP))
    srv.setACL(0, acls, groups, inherit)

    # 3. game server and team channels: allow after their "all deny" entry
    chans = srv.getChannels()
    games_root = next((c for c, ch in chans.items() if ch.name == "PR BF2 Game Servers"), None)
    n = 0
    for cid, ch in chans.items():
        if ch.name not in ("Team 1", "Team 2") and ch.parent != games_root:
            continue
        acls, groups, inherit = srv.getACL(cid)
        acls, groups = own(acls, groups)
        if not upsert(acls):
            acls.append(acl(GROUP))
        srv.setACL(cid, acls, groups, inherit)
        n += 1
    print("grant_bot: group '%s' allowed on Root and %d game/team channels" % (GROUP, n))
    print("grant_bot: reconnect the bot if it was registered just now")
    ic.destroy()


if __name__ == "__main__":
    main()
