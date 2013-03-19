#!/usr/bin/env python
"""Python IRC bot based loosely on XKCD's Bucket"""
import sys, re, random

from twisted.enterprise import adbapi 
from twisted.internet import reactor, protocol
from twisted.words.protocols import irc

from database_config import dbpool


class BucketBot(irc.IRCClient):
    def _get_nickname(self):
        return self.factory.nickname
    nickname = property(_get_nickname)


    def signedOn(self):
        self.join(self.factory.channel)
        print("Signed on as {0}.".format(self.nickname))


    def joined(self, channel):
        print("Joined {0}.".format(channel))


    def privmsg(self, user, channel, msg):
        user = user.split('!')[0]
        print("{0} <{1}> {2}".format(channel, user, msg))

        if msg.startswith(self.nickname) or channel == self.nickname:
            nick_length = len(self.nickname)
            if msg.find(self.nickname) == 0:
                # Strip off our nickname from the beginning
                msg = msg[nick_length:].lstrip(',: ')
            self.addressed(user, channel, msg)
        else:
            # Split the message up and find some facts
            words = msg.split()
            searches = []
            for word in words:
                if len(word) > 5:
                    searches.append(word)
            self.factoid(channel, random.choice(searches))

    def addressed(self, user, channel, msg):
        """Addressed by some user directly, by name or private message."""
        try:
            fact, tidbit = msg.split('is', 1)
            print("Learning {0} <is> {1}.".format(fact, tidbit))
            q = dbpool.runOperation('INSERT INTO facts (fact, tidbit, verb, RE, protected, mood, chance) VALUES (%s, %s, %s, False, True, NULL, NULL)',
                                    (fact.strip().lower(), 
                                     tidbit.strip(), 
                                     'is'))
            def success(success):
                print(success)
                self.msg(channel, "Okay, {0}.".format(user))
            def explode(failure):
                print(failure)
                self.msg(channel, "I'm sorry, {0}, something has gone terrible wrong and I can't find my mind.".format(user))
            q.addCallback(success)
            q.addErrback(explode)
        except ValueError:
            # Probably didn't understand the new factoid
            self.factoid(channel, "don't know")

    def factoid(self, target, fact):
        def say_factoid(result):
            if result:
                tidbit, verb = random.choice(result)
                if verb == '<reply>':
                    self.msg(target, tidbit)
                else:
                    self.msg(target, "{0} {1} {2}".format(fact, verb, tidbit))
            else:
                print("No matching factoid for {0}".format(fact))
        q = dbpool.runQuery('SELECT tidbit, verb FROM facts WHERE fact = %s;',
                            (fact.lower(),))
        q.addCallback(say_factoid)
            


class BucketBotFactory(protocol.ClientFactory):
    protocol = BucketBot

    def __init__(self, channel, nickname='Pail'):
        self.channel = channel
        self.nickname = nickname


    def clientConnectionLost(self, connector, reason):
        print("Lost connection (%s), reconnecting.".format(reason))
        connector.connect()


    def clientConnectionFailed(self, connector, reason):
        print("Could not connect: %s".format(reason))


if __name__ == "__main__":
    chan = sys.argv[1]
    reactor.connectTCP('irc.freenode.net', 6667, BucketBotFactory(chan))
    reactor.run()
