"""Port mumo's prbf2 module from Python 2 to Python 3.

Reads the module from the live Docker volume copy and writes the ported file
into the new project. Every change is listed below; nothing else is touched,
so the module's behaviour stays the same.
"""
import ast

import sys

# usage: python port_prbf2.py <old prbf2.py from PRMurmur's mumo> <output prbf2.py>
SRC, DST = sys.argv[1], sys.argv[2]

text = open(SRC, encoding="utf-8-sig").read()  # utf-8-sig drops the BOM

EDITS = [
    # 1. The hashlib/json fallbacks only existed for Python < 2.6.
    ("""try:
    from hashlib import sha1 as hashfunc
except: # Fallback for python < 2.6
    from _sha import new as hashfunc

try:
    import json
except ImportError: # Fallback for python < 2.6
    import simplejson as json
""",
     """import json

from hashlib import sha1 as hashfunc
"""),

    # 1b. Upstream mumo moved x2bool from mumo_module to config.
    ("""from mumo_module import (MumoModule,
                         x2bool)""",
     """from mumo_module import MumoModule
from config import x2bool"""),

    # 1c. '\\d' in a plain string is an invalid escape in Python 3.12+.
    ("lambda x: re.match('g\\d+', x):(",
     "lambda x: re.match(r'g\\d+', x):("),

    # 2. Python 3 exception syntax.
    ("except (ValueError, KeyError, AttributeError), e:",
     "except (ValueError, KeyError, AttributeError) as e:"),
    ("except (KeyError, ValueError), e:",
     "except (KeyError, ValueError) as e:"),

    # 3. basestring is gone; every string is str.
    ('verify(context, "ipport", basestring)',
     'verify(context, "ipport", str)'),
    ('verify(identity, "team", basestring)',
     'verify(identity, "team", str)'),

    # 4. hashlib takes bytes, not str. The hashed text is the same, so the
    #    password the game computes still matches.
    ("""                    hashfunc(
                    str(minutesSinceEpoch + i) + hash + secret
                ).digest()[0:4])[0] & 0x7FFFFF""",
     """                    hashfunc(
                    (str(minutesSinceEpoch + i) + hash + secret).encode("utf-8")
                ).digest()[0:4])[0] & 0x7FFFFF"""),
]

for old, new in EDITS:
    if text.count(old) != 1:
        raise SystemExit(f"не найдено ровно один раз ({text.count(old)}): {old[:60]!r}")
    text = text.replace(old, new)

ast.parse(text)  # must be valid Python 3 now
open(DST, "w", encoding="utf-8", newline="\n").write(text)
print(f"готово: {len(EDITS)} правок, {text.count(chr(10)) + 1} строк, синтаксис Python 3 проверен")
