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
    def nicks(self):
        return sorted(u.nick for u in self.members.values())

    @property
    def languages(self):
        return set(u.language for u in self.members.values())

    @property
    def users(self):
        return self.members.values()

    def userNick(self, jid):
        rv = None
        for u in self.members.values():
            if u.jid == jid:
                rv = u.nick
        return rv
