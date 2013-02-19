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
        # Separates the line into its four parts
        line_string = " ".join(line)
        parser = re.compile("^(?::(\S+)!\S+ )?(\S+)(?: (?!:)(.+?))?(?: :(.+))?$", re.MULTILINE)
        r = re.search(parser, line_string)
        irc_prefix = r.group(1)
        irc_command = r.group(2)
        irc_params = r.group(3)
        irc_trailing = r.group(4)
        
        # Verify a message was sent
        if irc_trailing != None:
            # Check if the command was sent via private message to the bot
            if irc_params == self._bot_nick:
                private = True
            else:
                private = False
                
            command = ""
            command_type = ""
            command_regex = re.compile("(?:!(\S+))",re.IGNORECASE)
            if private:
                command_type = "private"
                # First check if there's a exclamation-type command
                command_r = re.search(command_regex, irc_trailing)
                if command_r != None:
                    # Exclamation type command was found
                    command = command_r.group(1)
                else:
                    # No exclamation-type command; assume first word of message
                    command_r = re.search("(\S+)", irc_trailing)
                    command = command_r.group(1)
            else:
                # Check if command was addressed to the bot (with or without exclamation)
                command_regex = "{}(?::|,|)\s(?:!?(\S+))".format(self._bot_nick)
                command_r = re.search(command_regex, irc_trailing)
                if command_r != None:
                    # Directly-addressed command found
                    command_type = "direct"
                    command = command_r.group(1)
                else:
                    # Check for exclamation command
                    command_r = re.search("!(\S+)", irc_trailing)
                    if command_r != None:
                        # Exclamation command found
                        if command_r.start(1) == 1:
                            # Exclamation command at beginning of message
                            command_type = "exclamation_first"
                        else:
                            # Command is elsewhere in message
                            command_type = "exclamation"
                        command = command_r.group(1)
                        
            if command != "":
                if command in self.command_list:
                    module_name = self.command_list[command]
                    exec_string = "{0}(self._connection,'{1}','{2}','{3}','{4}')".format(module_name, irc_prefix,
                                                                                       irc_params, command_type,
                                                                                       irc_trailing)
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
                    exec("self.command_list['{0}'] = '{1}.{0}'".format(module_command, module))
        self._connection._commands = self.command_list
            
    def nickserv_parse(self, line):
        '''Parses a message from NickServ and responds accordingly.'''
        if "identify" in line:
            self.logger.info("NickServ has requested identification.")
            self._connection.nickserv_identify()
        elif "identified" in line:
            self._connection._password = self._connection._tentative_password
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
            self._connection.shut_down()
        elif numcode == "442":
            # ERR_NOTONCHANNEL - You're not in that channel
            self.logger.info("You tried to part from {}, but you are not in that "
                             "channel.".format(line[3]))
        elif numcode == "470":
            self.logger.error("Unable to join channel {}.".format(line[3]))
            self.logger.info("You were forwarded to {}. Parting from this channel.".format(line[4]))
            self._connection.part(line[4])
