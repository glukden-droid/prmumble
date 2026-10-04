#!/usr/bin/env python3
# Diagnostic: joins the server as a bot with the same plugin context as the
# players in the busiest squad channel, sits in that channel (moved there
# over Ice) and reports, per talking user, whether the voice packets the
# server forwards to a legacy client carry positional data and which target
# value they use. Needs pymumble inside the container:
#   pip3 install --break-system-packages pymumble  (plus libopus0)
#
#   docker exec prmurmur15 python3 /opt/scripts/voice_probe.py [seconds]

import base64, collections, configparser, ssl, sys, time

def _wrap(sock, certfile=None, keyfile=None, ssl_version=None):
    c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c.wrap_socket(sock)
ssl.wrap_socket = _wrap

import Ice
import pymumble_py3
from pymumble_py3 import mumble_pb2
from pymumble_py3.constants import PYMUMBLE_MSG_TYPES_USERSTATE

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 60

cfg = configparser.ConfigParser()
cfg.read("/data/mumo/mumo.ini")
port = 64740
for line in open("/data/mumble-server.ini"):
    if line.startswith("port="):
        port = int(line.split("=", 1)[1])

Ice.loadSlice("", ["-I" + Ice.getSliceDir(), "/usr/share/MumbleServer.ice"])
import MumbleServer as M
p = Ice.createProperties()
p.setProperty("Ice.ImplicitContext", "Shared")
p.setProperty("Ice.Default.EncodingVersion", "1.0")
d = Ice.InitializationData(); d.properties = p
ic = Ice.initialize(d)
ic.getImplicitContext().put("secret", cfg["ice"]["secret"])
srv = M.MetaPrx.checkedCast(ic.stringToProxy(
    "Meta:tcp -h 127.0.0.1 -p " + cfg["ice"]["port"])).getServer(1)

# busiest channel with in-game players, and their exact context bytes
users = srv.getUsers().values()
bych = collections.Counter(u.channel for u in users if u.context)
if not bych:
    sys.exit("probe: nobody with a plugin context on the server")
chan, n = bych.most_common(1)[0]
ctx = next(u.context for u in users if u.channel == chan and u.context)
try:
    raw = base64.b64decode(ctx, validate=True)
except Exception:
    raw = ctx.encode("latin-1")
print("probe: channel %d (%d players), context %r" % (chan, n, raw))

stats = collections.defaultdict(lambda: collections.Counter())

def varint(b, i):
    v = b[i]
    if v & 0x80 == 0: return v, i + 1
    if v & 0xC0 == 0x80: return ((v & 0x3F) << 8) | b[i + 1], i + 2
    if v & 0xE0 == 0xC0: return ((v & 0x1F) << 16) | (b[i + 1] << 8) | b[i + 2], i + 3
    if v & 0xF0 == 0xE0: return ((v & 0x0F) << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3], i + 4
    if v & 0xFC == 0xF0: return int.from_bytes(b[i + 1:i + 5], "big"), i + 5
    raise ValueError("varint")

def on_sound(self, message):
    try:
        b = bytes(message)
        typ, target = b[0] >> 5, b[0] & 0x1F
        sess, i = varint(b, 1)
        _, i = varint(b, i)            # sequence
        if typ == 4:                   # opus
            size, i = varint(b, i)
            i += size & 0x1FFF
        else:                          # celt/speex frames
            while True:
                h = b[i]; i += 1 + (h & 0x7F)
                if not h & 0x80: break
        rest = len(b) - i
        s = stats[sess]
        s["packets"] += 1
        s["target%d" % target] += 1
        s["with_position" if rest >= 12 else "no_position"] += 1
    except Exception as e:
        stats["parse_error"][repr(e)[:60]] += 1

pymumble_py3.Mumble.sound_received = on_sound

m = pymumble_py3.Mumble("127.0.0.1", "voiceprobe", port=port, reconnect=False)
m.start(); m.is_ready(); time.sleep(1)
us = mumble_pb2.UserState()
us.session = m.users.myself_session
us.plugin_context = raw
m.send_message(PYMUMBLE_MSG_TYPES_USERSTATE, us)
time.sleep(1)
me = srv.getState(m.users.myself_session)
me.channel = chan
srv.setState(me)
print("probe: listening %d s ..." % SECONDS)
time.sleep(SECONDS)

names = {s: u.name for s, u in srv.getUsers().items()}
for sess, c in stats.items():
    print("%-28s %s" % (names.get(sess, sess), dict(c)))
if not stats:
    print("probe: nobody talked in that channel")
m.stop(); ic.destroy()
