import time
import copy
from collections import defaultdict

from twisted.python import log
from twisted.internet import protocol, reactor, threads, defer
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import IQ

from wokkel.xmppim import MessageProtocol, PresenceClientProtocol
from wokkel.xmppim import Presence

import chatroom

class TranslateMUCMessageProtocol(MessageProtocol):

    def __init__(self, jid):
        super(TranslateMUCMessageProtocol, self).__init__()
        self.jid = jid.full()

    def connectionInitialized(self):
        super(TranslateMUCMessageProtocol, self).connectionInitialized()
        log.msg("Connected!")

        chatroom.chatrooms = {}

    def connectionLost(self, reason):
        log.msg('Disconnected!')
        chatroom.chatrooms = {}

    def sendOneMessage(self, recipient, room_name, sender, content):
        msg = domish.Element((None, "message"))
        msg["to"] = recipient
        msg['from'] = "%s@%s/%s" % (room_name, self.jid, sender)
        msg["type"] = 'groupchat'
        msg.addElement("body", content=content)
        msg.addElement(('http://jabber.org/protocol/nick', 'x'), content=sender)

        self.send(msg)

    def broadcastMessage(self, room, sender_nick, msg):
        for user in room.users:
            self.sendOneMessage(user.jid, room.name, sender_nick, msg)

    def processCommand(self, body, msg):
        cmd, args = body.split(' ', 2)
        log.msg("Processing cmd:  ``%s'' with ``%s''" % (cmd, args))
        tojid = JID(msg['to'])
        room = chatroom.chatrooms[tojid.user]
        user = room.members[msg['from']]

        if cmd == 'lang':
            log.msg("Setting user language to %s" % args)
            user.language=args

    @defer.deferredGenerator
    def translateAndSend(self, body, msg):
        tojid = JID(msg['to'])

        room_name = tojid.user
        room = chatroom.chatrooms[room_name]
        user = room.members[msg['from']]

        if user.language:
            log.msg("Room name:  %s, user nick:  %s"
                    % (room.name, user.nick))

            wfd = defer.waitForDeferred(room.translate(user.language, body))
            yield wfd

            translations = wfd.getResult()

            log.msg("Translations:  %s" % translations)

            targets = room.targets

            for lang, text in translations.iteritems():
                log.msg("Doing %s translation:  %s" % (lang, text))
                for u in targets[lang]:
                    log.msg("  Recipient:  %s" % u.jid)
                    self.sendOneMessage(u.jid, room.name, user.nick, text)

        else:
            self.sendOneMessage(user.jid, room.name, '*system*',
                                "You must specify a language before speaking.\n\n"
                                "For example:\n"
                                "/lang en")

    def onMessage(self, msg):
        log.msg("Got a message")
        if msg.getAttribute("type") == 'groupchat' and hasattr(msg, "body") and msg.body:
            body_text = unicode(msg.body)
            if body_text[0] == '/':
                self.processCommand(body_text[1:], msg)
            else:
                self.translateAndSend(body_text, msg)

class TranslateMUCPresenceProtocol(PresenceClientProtocol):

    started = time.time()
    connected = None
    lost = None
    num_connections = 0

    def __init__(self, jid):
        super(TranslateMUCPresenceProtocol, self).__init__()
        self.jid = jid.full()

    def connectionInitialized(self):
        super(TranslateMUCPresenceProtocol, self).connectionInitialized()
        self.connected = time.time()
        self.lost = None
        self.num_connections += 1
        # self.update_presence()

    def connectionLost(self, reason):
        self.connected = None
        self.lost = time.time()

    def subscribedReceived(self, entity):
        log.msg("Subscribe received from %s" % (entity.userhost()))

    def unsubscribedReceived(self, entity):
        log.msg("Unsubscribed received from %s" % (entity.userhost()))

    def subscribeReceived(self, entity):
        log.msg("Subscribe received from %s" % (entity.userhost()))

    def unsubscribeReceived(self, entity):
        log.msg("Unsubscribe received from %s" % (entity.userhost()))

    def _onPresenceProbe(self, presence):
        log.msg("I got probed.")

    def sendOnePresence(self, room_name, nick, role, recipient, presenceType):
        p = Presence(recipient, presenceType)
        p['from'] = "%s@%s/%s" % (room_name, self.jid, nick)
        x = p.addElement(('http://jabber.org/protocol/muc#user', 'x'))
        item = x.addElement('item')
        item['affiliation'] = 'none'
        item['role'] = role

        self.send(p)

    def presenceBroadcast(self, room_name, nick, presenceType=None):
        if chatroom.chatrooms.has_key(room_name):
            room = chatroom.chatrooms[room_name]
            for r in (u.jid for u in room.users):
                rjid = JID(r)
                self.sendOnePresence(room_name, nick, 'participant', rjid,
                                     presenceType)

    def _onPresenceAvailable(self, presence):
        fromjid = JID(presence['from'])
        tojid = JID(presence['to'])

        log.msg("Available from:  %s to %s (my jid is %s)"
                % (fromjid, tojid, self.jid))

        room_name = tojid.user

        log.msg("Room name:  %s, user nick:  %s, host: %s"
                % (room_name, tojid.resource, tojid.host))

        assert tojid.host == self.jid
        if room_name not in chatroom.chatrooms:
            chatroom.chatrooms[room_name] = chatroom.ChatRoom(room_name)
        chatroom.chatrooms[room_name].add(chatroom.ChatUser(
                tojid.resource, fromjid.full()))

        self.presenceBroadcast(room_name, tojid.resource)

    def _onPresenceUnavailable(self, presence):
        fromjid = JID(presence['from'])
        tojid = JID(presence['to'])

        log.msg("Unavailable from:  %s to %s (my jid is %s)"
                % (fromjid, tojid, self.jid))

        room_name = tojid.user

        log.msg("Room name:  %s, user nick:  %s, host: %s"
                % (room_name, tojid.resource, tojid.host))

        assert tojid.host == self.jid

        self.presenceBroadcast(room_name, tojid.resource, 'unavailable')

        room = chatroom.chatrooms[room_name]
        del room[fromjid.full()]
