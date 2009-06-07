from collections import defaultdict

from twisted.internet import defer
from twisted.python import log
from twisted.words.protocols.jabber.xmlstream import IQ
from twisted.words.protocols.jabber.jid import JID

from wokkel import data_form

chatrooms = {}

class TranslationMessage(IQ):
    def __init__(self, stream, fromjid, tojid, inlang, out_langs, text):
        super(TranslationMessage, self).__init__(stream, 'set')

        self['from'] = fromjid
        self['to'] = tojid

        command = self.addElement(('http://jabber.org/protocol/commands',
                                  "command"))
        command['node'] = 'translate'
        command['status'] = 'executing'

        form = data_form.Form('submit')
        form.addField(data_form.Field(var='in', value=inlang))
        form.addField(data_form.Field(var='out', values=out_langs))
        form.addField(data_form.Field(var='text', value=text))

        command.addChild(form.toElement())

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
        if user.jid not in self.members:
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

    def translate(self, stream, myjid, transjid, language, message):
        """Translate a message for all possible target languages"""

        log.msg("Translating %s from %s" % (message, language))

        targets = [l for l in self.targets.keys() if l != language]

        def handleResponse(res):
            log.msg("Handling a response")
            cmd = res.firstChildElement()
            assert cmd.name == 'command'
            assert cmd['node'] == 'translate'
            form = data_form.Form.fromElement(
                [e for e in cmd.elements('jabber:x:data', 'x')][0])

            rv = form.getValues()
            rv[language] = message

            log.msg("Translation response: %s" % rv)

            return rv

        m = TranslationMessage(stream, myjid, transjid, language,
                               targets, message)

        return m.send().addCallback(handleResponse)

