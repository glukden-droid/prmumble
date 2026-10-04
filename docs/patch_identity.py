#!/usr/bin/env python3
# Patches Mumble 1.5 server sources so it behaves like PR's own PRMurmur 1.2
# for the launcher HUD: every player's plugin identity (in-game name) and
# in-game position (UserState field 20) go to the other clients.
#
# The PR client (PRMumble) reads "name" from the identity of the user who is
# talking to show the in-game name on the HUD. Stock Mumble keeps identities
# server-side only, so the HUD stays empty.
#
# PRMurmur 1.2 (checked in prmurmurd.x64, Ghidra):
#  - msgUserState clears plugin_context but keeps plugin_identity and
#    broadcasts the message;
#  - msgAuthenticate puts plugin_identity of every user into the initial user
#    list sent to a new client.
#
#   patch_identity.py <mumble source dir>

import re
import sys

path = sys.argv[1].rstrip("/") + "/src/murmur/Messages.cpp"
src = open(path, encoding="utf-8").read()

# 1. msgUserState: keep the identity in the message and broadcast it.
old = re.compile(r"(pDstServerUser->qsIdentity\s*=\s*u8\(msg\.plugin_identity\(\)\);)"
                 r"(\s*(?://[^\n]*\n\s*)*)msg\.clear_plugin_identity\(\);")
src, n1 = old.subn(r"\1\2bBroadcast = true; // PR: identity goes to all clients", src)

# 2. msgAuthenticate: identities of present users in the initial user list.
start = src.index("void Server::msgAuthenticate(")
end = src.index("\nvoid Server::", start + 1)
body = src[start:end]
hashline = re.compile(r"(\n(\s*)if \(!u->qsHash\.isEmpty\(\)\)\s*\n?\s*mpus\.set_hash\(u8\(u->qsHash\)\);)")
body, n2 = hashline.subn(
    r"\n\2if (!u->qsIdentity.isEmpty()) // PR: send identities to the new client"
    r"\n\2\tmpus.set_plugin_identity(u8(u->qsIdentity));\1", body, count=1)
src = src[:start] + body + src[end:]

# 3. Player position. The PR client sends its in-game position as UserState
#    field 20 (repeated float); the launcher HUD needs it to show who is
#    talking, and PRMurmur broadcast every UserState that carried it.
#    Mumble 1.5 uses 20 for temporary_access_tokens (repeated string), which
#    makes the parser drop the floats. Give 20 back to PR's position and move
#    the tokens to a free number (PR clients never send tokens).
#
#    Unlike PRMurmur, the position is NOT broadcast: a modified client could
#    collect enemy positions (radar). It goes only to the users in the
#    sender's channel and the channels linked to it - his own team (team
#    channels are linked to their Commander and squad channels). That is
#    exactly the set the PR client reads for the HUD, and teammates see each
#    other on the in-game map anyway. The rest of the message is handled as
#    usual, without the position.
POSITION_RELAY = r"""
\1// PR: in-game position only to the sender's own and linked channels
\1if (msg.position_size() > 0) {
\1	MumbleProto::UserState mpPos;
\1	mpPos.set_session(pDstServerUser->uiSession);
\1	*mpPos.mutable_position() = msg.position();
\1	msg.clear_position();
\1	const QSet< Channel * > team = pDstServerUser->cChannel->allLinks();
\1	for (ServerUser *u : qhUsers) {
\1		if (u != pDstServerUser && u->sState == ServerUser::Authenticated && team.contains(u->cChannel))
\1			sendMessage(u, mpPos);
\1	}
\1}
"""
start = src.index("void Server::msgUserState(")
end = src.index("\nvoid Server::", start + 1)
body = src[start:end]
body, n3 = re.subn(
    r"\n(\s*)if \(bBroadcast\) \{",
    lambda m: POSITION_RELAY.replace("\\1", m.group(1)) + "\n" + m.group(1) + "if (bBroadcast) {",
    body, count=1)
src = src[:start] + body + src[end:]

proto_path = sys.argv[1].rstrip("/") + "/src/Mumble.proto"
proto = open(proto_path, encoding="utf-8").read()
proto, n4 = re.subn(
    r"repeated string temporary_access_tokens = 20;",
    "repeated string temporary_access_tokens = 120; // PR: 20 is position\n"
    "\t// PR: in-game position sent by the PR client, relayed to the team\n"
    "\trepeated float position = 20;", proto)

if (n1, n2, n3, n4) != (1, 1, 1, 1):
    sys.exit("patch_identity: expected 1 of each replacement, got %d %d %d %d" % (n1, n2, n3, n4))
open(proto_path, "w", encoding="utf-8").write(proto)
open(path, "w", encoding="utf-8").write(src)
print("patch_identity: Messages.cpp patched")
