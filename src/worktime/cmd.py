#  Worktime - a simple command line program for time tracking
#  Copyright (C) 2021 Thibault North <thibault@north.li>
#
#  This file is part of Worktime.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Worktime.  If not, see <http://www.gnu.org/licenses/>.

import cmd2

from prettytable import PrettyTable
from collections import Counter
from cmd2 import (
    ansi,
)
from typing import (
    List,
)

from worktime.record import (
    ArgType,
    CmdParser,
)
try:
    from typeguard import typechecked
except ImportError:
    # typechecked is a no-op
    def typechecked(func):
        def inner():
            func()
        return inner

class WorkCmd(cmd2.Cmd):
    '''
    Command line interface
    '''
    def __init__(self, cmd_parser: CmdParser) -> None:
        super().__init__()
        self.cmd_parser = cmd_parser

    @typechecked
    def do_stats(self, args: cmd2.parsing.Statement) -> None:
        '''
        Process a given stats command.
        '''
        ret = self.cmd_parser.parse_cmd("stats", args.split(" "))
        self.poutput(ret)

    @staticmethod
    @typechecked
    def last_option(line: str, begidx: int, endidx: int) -> str:
        return line.strip().split(" ")[-1] if endidx == begidx else line.split(" ")[-2]

    @typechecked
    def complete_stats(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Complete stats:
        - first suggest an option among [today, week, lastweek, ...]
        - then suggest a time offset [-1, +1, ...]
        '''
        last_option = self.last_option(line, begidx, endidx)
        
        if last_option in self.cmd_parser.stats_actions:
            if self.cmd_parser.stats_actions[last_option]["complete"] is None: return []
            offset_options = self.cmd_parser.stats_actions[last_option]["complete"]()
            avail_options = [k for k in offset_options if k.startswith(line[begidx:endidx])]
            return avail_options
        # Otherwise suggest option (today, etc.)
        show_act = Counter(self.cmd_parser.stats_actions.keys())
        prev_args = Counter(line.split(" "))
        if prev_args:
            avail_options = list(show_act - prev_args)
            return [k for k in avail_options if k.startswith(line[begidx:endidx])]

        else:
            return self.cmd_parser.stats_actions["complete"]

    @typechecked
    def do_edit(self, args: cmd2.parsing.Statement) -> None :
        '''
        Process an edit command
        '''
        ret = self.cmd_parser.parse_cmd("edit", args.split(" "))
        self.poutput(ret)

    @typechecked
    def complete_edit(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Autocompletion for the edit command
        '''
        last_option = self.last_option(line, begidx, endidx)

        # Complete values for option "id", "project", "from", "to" 
        #self.poutput("Last option: {}, begidx: {}, endidx: {}".format(last_option, begidx, endidx))
        if last_option in self.cmd_parser.edit_actions:
            # Provide options
            items = self.cmd_parser.edit_actions[last_option]["complete"]()
            sel_items = [k for k in items
                        if k.startswith(line[begidx:endidx])
                        ]
            return sel_items

        # Otherwise suggest options
        edit_act = Counter(self.cmd_parser.edit_actions.keys())
        prev_args = Counter(line.split(" "))
        #print(prev_args)
        if prev_args:
            avail_options = list(edit_act - prev_args)
            return [k for k in avail_options if k.startswith(line[begidx:endidx])]
        else:
            return self.cmd_parser.edit_actions["complete"]

    @typechecked
    def do_rm(self, args: cmd2.parsing.Statement) -> None:
        '''
        Process a rm command
        '''
        ret = self.cmd_parser.parse_cmd("rm", args.split(" "))
        self.poutput(ret)

    @typechecked
    def complete_rm(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Autocompletion for the rm command
        '''
        # Not implemented yet
        return self.cmd_parser.delete_actions["id"]["complete"]()

    @typechecked
    def do_show(self, args: cmd2.parsing.Statement) -> None:
        '''
        Process a show command        
        '''
        #print("Executing: show {}".format(args))
        ret = self.cmd_parser.parse_cmd("show",  args.split(" "))
        self.poutput(ret)

    @typechecked
    def complete_show(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Complete show:
        - first suggest an option among [today, week, ...]
        - then suggest a time offset [-1, +1, ...]
        '''
        last_option = self.last_option(line, begidx, endidx)
        
        if last_option in self.cmd_parser.show_actions:
            if self.cmd_parser.show_actions[last_option]["complete"] is None: return []
            offset_options = self.cmd_parser.show_actions[last_option]["complete"]()
            avail_options = [k for k in offset_options if k.startswith(line[begidx:endidx])]
            return avail_options
        # Otherwise suggest option (today, etc.)
        show_act = Counter(self.cmd_parser.show_actions.keys())
        prev_args = Counter(line.split(" "))
        if prev_args:
            avail_options = list(show_act - prev_args)
            return [k for k in avail_options if k.startswith(line[begidx:endidx])]

        else:
            return self.cmd_parser.show_actions["complete"]

    @typechecked
    def do_work(self, args: cmd2.parsing.Statement) -> None:
        '''
        Process a work command
        '''

        #print("Executing: work: {}".format(args))
        ret = self.cmd_parser.parse_cmd("work",  args.split(" "))
        self.poutput(ret)

    @typechecked
    def complete_work(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Autocompletion for the complete command
        '''
        # If "done", no other argument should be available
        # "done" can only be used alone
        # self.poutput("text: '{}', line: '{}', start_idx : {}, end_idx: {}".format(text, line, begidx, endidx))

        last_option = self.last_option(line, begidx, endidx)
        #self.poutput("last: '{}'".format(last_full_arg))

        if last_option == "done":
            return []

        # Complete values for option "on", "for" etc. from database
        #self.poutput("Last option: {}, begidx: {}, endidx: {}".format(last_option, begidx, endidx))
        if last_option in self.cmd_parser.work_actions:
            # Provide options
            all_projects = self.cmd_parser.work_actions[last_option]["complete"]()
            projects = [k for k in all_projects
                        if k.startswith(line[begidx:endidx])
                        ]
            return projects

        # Otherwise suggest options
        work_act = Counter(self.cmd_parser.work_actions.keys())
        prev_args = Counter(line.split(" "))
        #print(work_act)
        #print(prev_args)
        if prev_args:
            return list(work_act - prev_args)
        else:
            return self.cmd_parser.work_actions["complete"]

    @typechecked
    def do_project(self, args: cmd2.parsing.Statement) -> None:
        '''
        Execute a project command
        '''
        ret = self.cmd_parser.parse_cmd("project",  args.split(" "))
        self.poutput(ret)

    @typechecked
    def complete_project(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Autocompletion for the project command

        project list
        project rm <id>
        project add <project_name> (must be Project.subproject.Foobar)
        project id <id> moveinto <project_name>
        '''

        last_option = self.last_option(line, begidx, endidx)

        # Complete values for option "id", "project", "from", "to" 
        #self.poutput("Last option: {}, begidx: {}, endidx: {}".format(last_option, begidx, endidx))
        if last_option in self.cmd_parser.projects_actions:
            # Provide options
            if self.cmd_parser.projects_actions[last_option]["type"] == ArgType.Final:
                return []
            items = self.cmd_parser.projects_actions[last_option]["complete"]()
            sel_items = [k for k in items
                        if k.startswith(line[begidx:endidx])
                        ]
            return sel_items

        # Otherwise suggest options
        proj_act = Counter(self.cmd_parser.projects_actions.keys())
        prev_args = Counter(line.split(" "))
        #print(prev_args)
        if prev_args:
            avail_options = list(proj_act - prev_args)
            # Exclude actions which have no further argument
            if "add" in prev_args or "rm" in prev_args or "list" in prev_args:
                return []
            if "id" in prev_args:
                return ["rename"]
            return [k for k in avail_options if k.startswith(line[begidx:endidx])]
        else:
            return self.cmd_parser.edit_actions["complete"]
