#!/usr/bin/env python
"""Python IRC bot based loosely on XKCD's Bucket"""
import sys
import re
import random

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
            if len(msg) > 4:
                self.factoid(channel, [msg])
            elif msg == "...":
                self.factoid(channel, [])


    def addressed(self, user, channel, msg):
        """Addressed by some user directly, by name or private message."""
        for verb in [' is ', ' are ', ' <reply> ', ' <action> ']:
            if msg.find(verb) != -1:
                print(msg, verb, msg.split(verb, 1))
                fact, tidbit = msg.split(verb, 1)
                break
        try:
            fact, tidbit
        except NameError:
            # No idea what they are saying at us
            self.failure(channel)
        else: 
            print("Learning ~ {0} {1} {2}.".format(fact, verb, tidbit))
            q = dbpool.runOperation('INSERT INTO facts (fact, tidbit, verb, RE, protected, mood, chance) VALUES (%s, %s, %s, False, True, NULL, NULL)',
                                    (fact, 
                                     tidbit, 
                                     verb.strip()))
            def success(success):
                print(success)
                self.msg(channel, "Okay, {0}.".format(user))
            def explode(failure):
                print(failure)
                self.msg(channel, "I'm sorry, {0}, something has gone terrible wrong and I can't find my mind.".format(user))
            q.addCallback(success)
            q.addErrback(explode)


    def failure(self, target):
        self.factoid(target, ["don't know"])


    def factoid(self, target, facts):
        # Search using only lowercase
        facts = [x.lower() for x in facts]
        def say_factoid(result):
            if result:
                fact_id, fact, verb, tidbit = result[0]
                if verb == '<reply>':
                    self.msg(target, tidbit)
                elif verb == '<action>':
                    self.ctcpMakeQuery(target, [('ACTION', tidbit)])
                else:
                    self.msg(target, "{0} {1} {2}".format(fact, verb, tidbit))
            else:
                print("No matching factoid for {0}".format(facts))

        BASE_SQL = "SELECT id, fact, verb, tidbit FROM facts "
        WHERE_SQL = "WHERE lower(fact) = ANY(%s) "
        RANDOM_SQL = "ORDER BY RANDOM() LIMIT 1;"
        #RANDOM_SQL = "OFFSET random() * (SELECT count(*) FROM facts) LIMIT 1;"
        if facts:
            SQL = BASE_SQL + WHERE_SQL + RANDOM_SQL
        else:
            SQL = BASE_SQL + RANDOM_SQL
        q = dbpool.runQuery(SQL,
                            (facts,))
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
