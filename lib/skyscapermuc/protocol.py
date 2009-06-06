import time
from collections import defaultdict

from twisted.python import log
from twisted.internet import protocol, reactor, threads
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import IQ

from wokkel.xmppim import MessageProtocol, PresenceClientProtocol
from wokkel.xmppim import Presence

from chatroom import ChatRoom, ChatUser

chatrooms = {}

class TranslateMUCMessageProtocol(MessageProtocol):

    def __init__(self, jid):
        super(TranslateMUCMessageProtocol, self).__init__()
        self.jid = jid.full()

    def connectionInitialized(self):
        super(TranslateMUCMessageProtocol, self).connectionInitialized()
        log.msg("Connected!")

        global chatrooms
        chatrooms = {}

    def connectionLost(self, reason):
        log.msg('Disconnected!')
        self.chatrooms = {}

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

    def onMessage(self, msg):
        log.msg("Got a message")
        if msg.getAttribute("type") == 'groupchat' and hasattr(msg, "body") and msg.body:
            tojid = JID(msg['to'])

            room_name = tojid.user
            room = chatrooms[room_name]
            nick = room.userNick(msg['from'])

            log.msg("Room name:  %s, user nick:  %s"
                    % (room.name, nick))

            self.broadcastMessage(room, nick, msg.body)

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
        global chatrooms
        if chatrooms.has_key(room_name):
            room = chatrooms[room_name]
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
        global chatrooms
        if room_name not in chatrooms:
            chatrooms[room_name] = ChatRoom(room_name)
        chatrooms[room_name].add(ChatUser(tojid.resource, fromjid.full()))

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

        global chatrooms
        room = chatrooms[room_name]
        del room[fromjid.full()]
