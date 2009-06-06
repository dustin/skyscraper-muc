from collections import defaultdict

from twisted.internet import defer
from twisted.python import log

chatrooms = {}

class ChatUser(object):

    def __init__(self, nick, jid, language=None):
        self.nick = nick
        self.jid = jid
        self.language = language

class ChatRoom(object):

    def __init__(self, name):
        self.name = name
        # jid -> ChatUser
        self.members = {}

    def __len__(self):
        return len(self.members)

    def add(self, user):
        self.members[user.jid] = user

    def __delitem__(self, jid):
        if jid in self.members:
            del self.members[jid]

    @property
    def targets(self):
        """Return a dict of language -> lists of users"""
        rv = defaultdict(list)
        for u in self.members.values():
            if u.language:
                rv[u.language].append(u)
        return rv

    @property
    def users(self):
        return self.members.values()

    def userNick(self, jid):
        rv = None
        for u in self.members.values():
            if u.jid == jid:
                rv = u.nick
        return rv

    def translate(self, language, message):
        """Translate a message for all possible target languages"""
        rv = {}

        log.msg("Translating %s from %s" % (message, language))

        for l in self.targets.keys():
            if l == language:
                rv[l] = message
            else:
                rv[l] = message + " (translated to " + l + ")"

        return defer.succeed(rv)
