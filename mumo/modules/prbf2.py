#!/usr/bin/env python
# -*- coding: utf-8

# Copyright (C) 2010 Stefan Hacker <dd0t@users.sourceforge.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:

# - Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# - Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# - Neither the name of the Mumble Developers nor the names of its
#   contributors may be used to endorse or promote products derived from this
#   software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# `AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#
# prbf2.py
# This module manages ACL/channel movements based on PR:BF2
# gamestate reported by PRMumble
#

from mumo_module import MumoModule
from config import x2bool

import re
import sys
import time
import struct


import json
import base64

from hashlib import sha1 as hashfunc

class prbf2(MumoModule):
    default_config = {'prbf2':(
                             ('gamecount', int, 1),
                             ('secret', str, ""),
                             ),
                      lambda x: re.match(r'g\d+', x):(
                             ('name', str, ''),
                             ('mumble_server', int, 1),
                             ('ipport_filter_negate', x2bool, False),
                             ('ipport_filter', str, ""), # support multiple ip's per channel for weird chinese servers :|
                             #('ipport_filter', re.compile, re.compile('.*')),
                             
                             ('base', int, 0),
                             ('left', int, -1),
                             
                             ('blufor', int, -1),
                             ('blufor_commander', int, -1),
                             ('blufor_no_squad', int, -1),
                             ('blufor_first_squad', int, -1),
                             ('blufor_first_squad_leader', int, -1),
                             ('blufor_second_squad', int, -1),
                             ('blufor_second_squad_leader', int, -1),
                             ('blufor_third_squad', int, -1),
                             ('blufor_third_squad_leader', int, -1),
                             ('blufor_fourth_squad', int, -1),
                             ('blufor_fourth_squad_leader', int, -1),
                             ('blufor_fifth_squad', int, -1),
                             ('blufor_fifth_squad_leader', int, -1),
                             ('blufor_sixth_squad', int, -1),
                             ('blufor_sixth_squad_leader', int, -1),
                             ('blufor_seventh_squad', int, -1),
                             ('blufor_seventh_squad_leader', int, -1),
                             ('blufor_eighth_squad', int, -1),
                             ('blufor_eighth_squad_leader', int, -1),
                             ('blufor_ninth_squad', int, -1),
                             ('blufor_ninth_squad_leader', int, -1),
                             
                             ('opfor', int, -1),
                             ('opfor_commander', int, -1),
                             ('opfor_no_squad', int, -1),
                             ('opfor_first_squad', int, -1),
                             ('opfor_first_squad_leader', int, -1),
                             ('opfor_second_squad', int, -1),
                             ('opfor_second_squad_leader', int, -1),
                             ('opfor_third_squad', int, -1),
                             ('opfor_third_squad_leader', int, -1),
                             ('opfor_fourth_squad', int, -1),
                             ('opfor_fourth_squad_leader', int, -1),
                             ('opfor_fifth_squad', int, -1),
                             ('opfor_fifth_squad_leader', int, -1),
                             ('opfor_sixth_squad', int, -1),
                             ('opfor_sixth_squad_leader', int, -1),
                             ('opfor_seventh_squad', int, -1),
                             ('opfor_seventh_squad_leader', int, -1),
                             ('opfor_eighth_squad', int, -1),
                             ('opfor_eighth_squad_leader', int, -1),
                             ('opfor_ninth_squad', int, -1),
                             ('opfor_ninth_squad_leader', int, -1)
                             ),
                    }
    
    id_to_squad_name = ["no", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth"]
    
    def __init__(self, name, manager, configuration = None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()

    def connected(self):
        cfg = self.cfg()
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")
        
        servers = set()
        for i in range(cfg.prbf2.gamecount):
            try:
                servers.add(cfg["g%d" % i].mumble_server)
            except KeyError:
                log.error("Invalid configuration. Game configuration for 'g%d' not found.", i)
                return
        
        self.sessions = {} # {serverid:{sessionid:laststate}}
        manager.subscribeServerCallbacks(self, servers)
        manager.subscribeMetaCallbacks(self, servers)
    
    def disconnected(self): pass

    def ready(self, server):
        log = self.log()
        log.debug("prbf2 ready, handling existing users")
        
        self.sessions = {}
        for index, user in server.getUsers().items():
            self.handle(server, user)
    
    #
    #--- Module specific state handling code
    #
    def update_state(self, server, oldstate, newstate):
        log = self.log()
        sid = server.id()
        
        session = newstate.session
        newoldchannel = newstate.channel
        
        try:
            opc = oldstate.parsedcontext
            ogcfgname = opc["gamename"]
            ogcfg = opc["gamecfg"]
            og = ogcfg.name
            opi = oldstate.parsedidentity
        except (AttributeError, KeyError):
            og = None
            
            opi = {}
            opc = {}
            
        if oldstate and oldstate.is_linked:
            oli = True
        else:
            oli = False
        
        try:
            npc = newstate.parsedcontext
            ngcfgname = npc["gamename"]
            ngcfg = npc["gamecfg"]
            ng = ngcfg.name
            npi = newstate.parsedidentity
        except (AttributeError, KeyError):
            ng = None
            
            npi = {}
            npc = {}
            nli = False
        
        if newstate and newstate.is_linked:
            nli = True
        else:
            nli = False
        
        try:
            
            if not oli and nli:
                log.debug("User '%s' (%d|%d) on server %d now linked", newstate.name, newstate.session, newstate.userid, sid)
                server.addUserToGroup(0, session, "bf2_linked")

            # Groups as sets of (channel, group). The old code removed every
            # group and added them back on each identity update (the PR client
            # sends a new "pass" every ~20 s). In Mumble 1.5.517 every group
            # change runs clearACLCache(), which on regaining Speak broadcasts
            # suppress=TRUE to all clients (server bug) - players ended up
            # muted. Now only real differences are applied, new ones first.
            oldgroups = set()
            if opi and opc:
                squadname = self.id_to_squad_name[opi["squad"]]
                oldgroups = self.player_groups(ogcfg, og or ogcfgname, opi)
                channame = "left"
                newstate.channel = ogcfg["left"]

            newgroups = set()
            if npc and npi and self.verifyIdentity(npi["hash"], npi["pass"]):
                log.debug("Updating user '%s' (%d|%d) on server %d in game %s: %s", newstate.name, newstate.session, newstate.userid, sid, ng or ngcfgname, str(npi))
                newgroups = self.player_groups(ngcfg, ng or ngcfgname, npi)

                channame = "%s_%s_squad" % (npi["team"], self.id_to_squad_name[npi["squad"]])
                if npi["squad_leader"]:
                    channame = "%s_%s_squad_leader" % (npi["team"], self.id_to_squad_name[npi["squad"]])
                if npi["commander"]:
                    channame = "%s_commander" % npi["team"]
                newstate.channel = ngcfg[channame]

            for cid, group in sorted(newgroups - oldgroups):
                server.addUserToGroup(cid, session, group)
                log.debug("Added '%s' to group %s in %d", newstate.name, group, cid)
            for cid, group in sorted(oldgroups - newgroups):
                server.removeUserFromGroup(cid, session, group)
                log.debug("Removed '%s' from group %s in %d", newstate.name, group, cid)
            groupschanged = oldgroups != newgroups

            if oli and not nli:
                log.debug("User '%s' (%d|%d) on server %d no longer linked", newstate.name, newstate.session, newstate.userid, sid)
                server.removeUserFromGroup(0, session, "bf2_linked")
                    
            if newstate.channel >= 0:
                # Make the clients' view of "suppress" right. setState applies
                # newstate.suppress (from a possibly stale callback state), and
                # after a group change the server may have broadcast a wrong
                # suppress=true (see above).
                moved = newoldchannel != newstate.channel
                mayspeak = server.hasPermission(session, newstate.channel, 0x8)
                if moved:
                    if ng == None:
                        log.debug("Moving '%s' leaving %s to channel %s", newstate.name, og or ogcfgname, channame)
                    else:
                        log.debug("Moving '%s' @ %s to channel %s", newstate.name, ng or ngcfgname, channame)
                    # suppress=True then the channel change itself recomputes
                    # it from Speak and broadcasts the real value
                    newstate.suppress = True
                    server.setState(newstate)
                elif groupschanged or newstate.suppress == mayspeak:
                    log.debug("Syncing suppress of '%s' in channel %d: %s", newstate.name, newstate.channel, not mayspeak)
                    if mayspeak:
                        # set + clear so every client gets suppress=false
                        newstate.suppress = True
                        server.setState(newstate)
                    newstate.suppress = not mayspeak
                    server.setState(newstate)
        except:
            log.exception("Exception raised while updating '%s'", newstate.name)
            self.userDisconnected(server, oldstate)
            self.userDisconnected(server, newstate)
        
    def player_groups(self, gamecfg, gamename, identity):
        """Temporary groups mumo keeps for a player, as {(channel, group)}."""
        squadname = self.id_to_squad_name[identity["squad"]]
        team = gamecfg[identity["team"]]
        groups = {(gamecfg["base"], "bf2_%s_game" % gamename),
                  (team, "bf2_team"),
                  (team, "bf2_%s_squad" % squadname)}
        if identity["squad_leader"]:
            groups.add((team, "bf2_%s_squad_leader" % squadname))
            groups.add((team, "bf2_squad_leader"))
        if identity["commander"]:
            groups.add((team, "bf2_commander"))
            groups.add((team, "bf2_squad_leader"))
        return groups

    def handle(self, server, state):
        def verify(mdict, key, vtype):
            if not isinstance(mdict[key], vtype):
                raise ValueError("'%s' of invalid type" % key)
            
        if not state:
            return
        
        cfg = self.cfg()
        log = self.log()
        sid = server.id()
        
        # Add defaults for our variables to state
        state.parsedidentity = {}
        state.parsedcontext = {}
        state.is_linked = False
        
        if sid not in self.sessions: # Make sure there is a dict to store states in
            self.sessions[sid] = {}
        
        update = False
        if state.session in self.sessions[sid] and self.sessions[sid][state.session]:
            if state.identity != self.sessions[sid][state.session].identity or \
               state.context != self.sessions[sid][state.session].context:
                # identity or context changed => update
                update = True
            else: # id and context didn't change hence the old data must still be valid
                state.is_linked = self.sessions[sid][state.session].is_linked
                state.parsedcontext = self.sessions[sid][state.session].parsedcontext
                state.parsedidentity = self.sessions[sid][state.session].parsedidentity
        else:
            if state.identity or state.context:
                # New user with engaged plugin => update
                self.sessions[sid][state.session] = None
                update = True
                
        if not update:
            self.sessions[sid][state.session] = state
            return
            
        log.info("%s (%d|%d) %s", state.name, state.session, state.userid, state.context)
        # The plugin will always prefix "Project Reality: BF2\0" to the context for the PR:BF2 plugin
        # don't bother analyzing anything if it isn't there
        splitcontext = self.decodeContext(state.context).split('\0', 1)
        if splitcontext[0] == "Project Reality: BF2":
            state.is_linked = True
            if state.identity and len(splitcontext) == 1:
                #LEGACY: Assume broken Ice 3.2 which doesn't transmit context after \0
                splitcontext.append('{"ipport":""}') # Obviously this doesn't give full functionality but it doesn't crash either ;-)

        if state.is_linked and len(splitcontext) == 2 and state.identity: 
            try:
                context = json.loads(splitcontext[1])
                verify(context, "ipport", str)
                
                for i in range(cfg.prbf2.gamecount):
                    # Try to find a matching game
                    gamename = "g%d" % i
                    gamecfg = getattr(cfg, gamename)
                    
                    if gamecfg.mumble_server == server.id():
                        # support multiple ip's per channel for weird chinese servers :|
                        ipports = gamecfg.ipport_filter.split(',')
                        not_matched = True
                        for ipport in ipports:
                            if ipport == context["ipport"]:
                                not_matched = False
                                break
                        #not_matched = (gamecfg.ipport_filter.match(context["ipport"]) == None)
                        #if not_matched == gamecfg.ipport_filter_negate:
                        if not not_matched:
                            break
                    gamename = None
                
                if not gamename:
                    raise ValueError("No matching game found")
                
                context["gamecfg"] = gamecfg
                context["gamename"] = gamename
                state.parsedcontext = context

            except (ValueError, KeyError, AttributeError) as e:
                log.debug("Invalid context for %s (%d|%d) on server %d: %s", state.name, state.session, state.userid, sid, repr(e))
        
            try:
                log.debug("Identity of %s: %r", state.name, state.identity)
                identity = json.loads(state.identity)
                verify(identity, "commander", bool)
                verify(identity, "squad_leader", bool)
                verify(identity, "squad", int)
                if identity["squad"] < 0 or identity["squad"] > 9:
                    raise ValueError("Invalid squad number")
                verify(identity, "team", str)
                if identity["team"] != "opfor" and identity["team"] != "blufor":
                    raise ValueError("Invalid team identified")
                #LEGACY: Ice 3.2 cannot handle unicode strings
                identity["team"] = str(identity["team"])
                try:
                    identity["hash"] = str(identity["hash"])
                    identity["pass"] = str(identity["pass"])
                except: 
                    identity["hash"] = ""
                    identity["pass"] = ""
                
                state.parsedidentity = identity
                
            except (KeyError, ValueError) as e:
                log.debug("Invalid identity for %s (%d|%d) on server %d: %s", state.name, state.session, state.userid, sid, repr(e))

        # Update state and remember it
        self.update_state(server, self.sessions[sid][state.session], state)
        self.sessions[sid][state.session] = state
    
    #
    #--- Server callback functions
    #
    
    def userDisconnected(self, server, state, context = None):
        try:
            sid = server.id()
            del self.sessions[sid][state.session]
        except: pass
        try:
            server.kickUser(state.session, "User Disconnected")
        except: pass
         
    def userStateChanged(self, server, state, context = None):
        self.handle(server, state)
        
    def userConnected(self, server, state, context = None):
        self.handle(server, state)
    
    def channelCreated(self, server, state, context = None): pass
    def channelRemoved(self, server, state, context = None): pass
    def channelStateChanged(self, server, state, context = None): pass
    
    #
    #--- Meta callback functions
    #

    def started(self, server, context = None):
        self.sessions[server.id()] = {}
        
        if not cfg.murmur.servers or sid in cfg.murmur.servers:
            for index, user in server.getUsers().items():
                self.handle(server, user)
        
    def stopped(self, server, context = None):
        self.sessions[server.id()] = {}



    @staticmethod
    def decodeContext(context):
        # Mumble 1.5 hands the plugin context to Ice base64-encoded (it may be
        # binary); 1.2 passed it as is. Accept both.
        prefix = "Project Reality: BF2"
        if not context or context.startswith(prefix):
            return context
        try:
            decoded = base64.b64decode(context, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return context
        return decoded if decoded.startswith(prefix) else context

    def verifyIdentity(self, hash, password):
        log = self.log()
        cfg = self.cfg()
        secret = cfg.prbf2.secret
        if secret == "":
            log.debug("identity verification disabled")
            return True

        minutesSinceEpoch = int(time.time() / 60.0)
        # Try previous minute and next minute
        for i in range (-1, 2):
            p = struct.unpack("<i",
                    hashfunc(
                    (str(minutesSinceEpoch + i) + hash + secret).encode("utf-8")
                ).digest()[0:4])[0] & 0x7FFFFF
            if str(p) == password:
                log.debug("%s verified identity" % hash)
                return True

        log.warning("Failed verifying identity for %s (pass %s, minute %d)" % (hash, password, minutesSinceEpoch))
        return False