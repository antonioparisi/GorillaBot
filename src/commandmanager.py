# Copyright (c) 2013 Molly White
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from inspect import getmembers, isfunction
import logging
import re
import plugins
from plugins import *

__all__ = ["CommandManager"]

class CommandManager(object):
    
    def __init__(self, bot, connection):
        '''Determines if a message is in fact a command, stores a list of all valid commands.'''
        self._bot = bot
        self._connection = connection
        self._bot_nick = connection._nick
        self.logger = logging.getLogger("GorillaBot")
        self.command_list = {}
        self.organize_commands()
        
    def check_command(self, line):
        '''Messages of type PRIVMSG will be passed through this function to check if they are
        commands.'''
        
        # Format message more nicely
        raw_nick = line.pop(0)
        r = re.search(":(.*?)!", raw_nick)
        if r:
            sender = r.group(1)
        line.pop(0)
        private = False
        chan = line.pop(0)
        if chan == self._bot_nick:
            private = True
        line[0] = line[0][1:]
        # line is now a list containing just the message contents.
        
        # Check if a private message contains a command
        # First looks for words beginning with an exclamation point. If none are found, it assumes
        #     the first word of the message is the command.
        command = ""
        command_type = ""
        if private:
            for word in line:
                if word[0] == "!":
                    command = word[1:]
            if command == "":
                command = line[0]
            command_type = "private"
        # Check for a message directly addressed to the bot
        elif self._bot_nick in line[0]:
            if line[1][0] == "!":
                command = line[1][1:]
            else:
                command = line[1]
            command_type = "direct"
        #Check for a message preceded by an exclamation point
        else:
            for idx, word in enumerate(line):
                if word[0] == "!":
                    command = word[1:]
                    command_type = "exclamation"
                    if idx == 0:
                        command_type = "exclamation_first"
        
        if command != "":
            if command in self.command_list:
                module_name = self.command_list[command]
                exec_string = "{0}.{1}(self._connection,'{2}','{3}','{4}',{5})".format(module_name, command,
                                                              sender, chan, command_type, line)
                exec(exec_string)
            
    def organize_commands(self):
        '''Collects commands from the various plugins, organizes them into a dict.'''
        for module in plugins.__all__:
            module_command_list = []
            exec("module_command_list += [name for name, data in getmembers({0})"
                 "if isfunction(data)]".format(module))
            for module_command in module_command_list:
                
                # Prevents private functions from being displayed or executed from IRC
                if module_command[0] != "_":
                    exec("self.command_list['{0}'] = '{1}'".format(module_command, module))
            
    def nickserv_parse(self, line):
        '''Parses a message from NickServ and responds accordingly.'''
        if "identify" in line:
            self.logger.info("NickServ has requested identification.")
            self._connection.nickserv_identify()
        elif "identified" in line:
            self.logger.info("You have successfully identified as {}.".format(line[2]))
        elif ":Invalid" in line:
            self.logger.info("You've entered an incorrect password. Please re-enter.")
            self._connection.nickserv_identify()
    
    def process_numcode(self, numcode, line):
        '''Parses a message with a reply code number and responds accordingly.'''
        if numcode == "396":
            # RPL_HOSTHIDDEN - Cloak set.
            self.logger.info("Cloak set as {}.".format(line[3]))
        elif numcode == "403":
            # ERR_NOSUCHCHANNEL
            self.logger.warning("No such channel exists.")
        elif numcode == "433":
            # ERR_NICKNAMEINUSE - Nickname is already in use.
            # TODO: Change response to something more productive than shutting down.
            self.logger.error("Nickname is already in use. Closing connection.")
            self._connection.quit()
            self.connection.shut_down()
        elif numcode == "442":
            # ERR_NOTONCHANNEL - You're not in that channel
            self.logger.info("You tried to part from {}, but you are not in that "
                             "channel.".format(line[3]))
        elif numcode == "470":
            self.logger.error("Unable to join channel {}.".format(line[3]))
            self.logger.info("You were forwarded to {}. Parting from this channel.".format(line[4]))
            self._connection.part(line[4])
