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
        self.inventory = ['an old shoe']
        self.receive_item = re.compile(\
            """^(?:
                   puts \s (\S.+) \s in \s (the \s)? {0}\b
                 | (?:gives|hands) \s {0} \s (\S.+)
                 | (?:gives|hands) \s (\S.+) \s to {0}\b
                )""".format(self.nickname), re.X | re.I)
        self.join(self.factory.channel)
        print("Signed on as {0}.".format(self.nickname))


    def joined(self, channel):
        print("Joined {0}.".format(channel))


    def action(self, user, channel, action):
        self.privmsg(user, channel, action)


    def privmsg(self, user, channel, msg):
        user = user.split('!')[0]
        print("{0} <{1}> {2}".format(channel, user, msg))

        if msg.startswith(self.nickname):
            self.addressed(user, channel, msg)
        elif channel == self.nickname:
            # Private messages
            self.addressed(user, user, msg)
        else:
            if msg == "...":
                self.factoid(channel, user, [msg])
            else:
                self.command(channel, user, msg)


    def addressed(self, user, source, msg):
        """Addressed by some user directly, by name or private message."""
        nick_length = len(self.nickname)
        if msg.find(self.nickname) == 0:
            # Strip off our nickname from the beginning
            msg = msg[nick_length:].lstrip(',: ')
        for verb in [' is ', ' are ', ' <reply> ', ' <action> ']:
            if msg.find(verb) != -1:
                fact, tidbit = msg.split(verb, 1)
                break
        try:
            fact, tidbit
        except NameError:
            # Not learning
            self.command(source, user, msg, addressed=True)
        else: 
            print("Learning ~ {0} {1} {2}.".format(fact, verb, tidbit))
            q = dbpool.runOperation('INSERT INTO facts (fact, tidbit, verb, RE, protected, mood, chance) VALUES (%s, %s, %s, False, True, NULL, NULL)',
                                    (fact, 
                                     tidbit, 
                                     verb.strip()))
            def success(success):
                print(success)
                self.msg(source, "Okay, {0}.".format(user))
            def explode(failure):
                print(failure)
                self.msg(source, "I'm sorry, {0}, something has gone terrible wrong and I can't find my mind.".format(user))
            q.addCallback(success)
            q.addErrback(explode)


    def failure(self, target, source):
        self.factoid(target, source, ["don't know"])


    def command(self, target, source, msg, addressed=False):
        receive_item = self.receive_item.match(msg)
        if addressed and msg == "inventory":
            self.factoid(target, source, ["list items"])
        elif receive_item:
            # If any group matched, that's the item
            item = [x for x in receive_item.groups() if x != None]
            if item[0]:
                item = item[0]
                if item in self.inventory:
                    self.factoid(target, source, ['duplicate item'], item=item)
                elif len(self.inventory) > 8:
                    self.inventory.insert(0, item)
                    self.factoid(target, source, ['pickup full'], item=item)
                else:
                    self.inventory.insert(0, item)
                    self.factoid(target, source, ['takes item'], item=item)
        elif addressed or random.randrange(100) <= 5:
            self.factoid(target, source, [msg])


    def factoid(self, target, source, facts, addressed=False, item=None):
        # Search using only lowercase
        facts = [x.lower() for x in facts]
        def say_factoid(result):
            if result:
                fact_id, fact, verb, tidbit = result[0]
                tidbit = tidbit.replace("$who", source)
                tidbit = tidbit.replace("$inventory",
                                        ", ".join(self.inventory))
                if item:
                    tidbit = tidbit.replace("$item", item)
                if tidbit.find("$giveitem") != -1:
                    tidbit = tidbit.replace("$giveitem", self.inventory.pop())
                if verb == '<reply>':
                    self.msg(target, tidbit)
                elif verb == '<action>':
                    self.ctcpMakeQuery(target, [('ACTION', tidbit)])
                else:
                    self.msg(target, "{0} {1} {2}".format(fact, verb, tidbit))
            else:
                print("No matching factoid for {0}".format(facts))
                if addressed:
                    self.failure(target, source)

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
