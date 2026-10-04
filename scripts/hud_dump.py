#!/usr/bin/env python3
# Windows, client side: prints what PRMumble writes for the PR launcher HUD
# (Qt shared memory "PRMumbleSharedData", 32 KiB, UTF-8). One record per
# player in your channel and the channels linked to it, 8 fields:
#   name | channel | talk state | flag | flag | x | y | z
# talk state: 0 silent, 1 talking (local), 2 whispering, 3 shouting (radio).
# The launcher shows a record only if the state is 1..3 and the position is
# not 0,0,0; for state 1 also only within 70 m of you.
#
#   python scripts\hud_dump.py            (run while in game, Ctrl+C to stop)

import hashlib
import mmap
import sys
import time

KEY = "PRMumbleSharedData"
QT_NAME = "qipc_sharedmemory_" + "".join(c for c in KEY if c.isalpha()) \
          + hashlib.sha1(KEY.encode()).hexdigest()
SIZE = 32768


def open_shm():
    for name in [KEY + str(i) for i in range(1, 11)] + [QT_NAME, KEY]:
        try:
            m = mmap.mmap(-1, SIZE, tagname=name, access=mmap.ACCESS_READ)
            if m[:SIZE].strip(b"\0"):
                return name, m
            m.close()
        except OSError:
            pass
    return None, None


name, shm = open_shm()
if not shm:
    sys.exit("hud_dump: shared memory not found or empty - is PRMumble running "
             "and connected while you are in game?")
print("hud_dump: reading", name)
last = None
try:
    while True:
        text = shm[:SIZE].split(b"\0", 1)[0].decode("utf-8", "replace")
        rows = [r.split("\x01") for r in text.split("\x02") if r]
        talking = [r for r in rows if len(r) == 8 and r[2].strip() not in ("0", "")]
        snap = "\n".join(" | ".join(r) for r in talking)
        if snap != last:
            print(time.strftime("%H:%M:%S"), "records %d, talking %d" % (len(rows), len(talking)))
            if snap:
                print("   " + snap.replace("\n", "\n   "))
            last = snap
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
