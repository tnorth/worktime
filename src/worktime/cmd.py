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
    from typeguard import typechecked_
except ImportError:
    # typechecked is a no-op
    def typechecked(func):
        def inner(*args, **kwargs):
            return func(*args, **kwargs)
        return inner


class WorkCmd(cmd2.Cmd):
    '''
    Command line interface
    '''
    def __init__(self, cmd_parser: CmdParser) -> None:
        super().__init__()
        self.prompt = cmd_parser.define_prompt()
        self.cmd_parser = cmd_parser

    @typechecked
    def postcmd(self, stop: bool, line: str) -> bool:
        """Hook method executed just after a command dispatch is finished.

        :param stop: if True, the command has indicated the application should exit
        :param line: the command line text for this command
        :return: if this is True, the application will exit after this command and the postloop() will run
        """
        self.prompt = self.cmd_parser.define_prompt()
        return stop

    @typechecked
    def feedback(self, msg: str) -> None:
        """Wraps pfeedback, adds color"""
        self.pfeedback(ansi.style(msg, fg='bright_black'))

    @typechecked
    def print_output(self, cmd_res: dict) -> None:
        # Dictionaries are ordered in recent Python versions
        for item, func in {"output": self.poutput, "error": self.perror, "notify": self.feedback, "warning": self.pwarning}.items():
            if item in cmd_res and cmd_res[item] is not None:
                func(cmd_res[item])


    @typechecked
    def do_stats(self, args: cmd2.parsing.Statement) -> None:
        r'''
        Process a given stats command.

        Possible usage: 

            # Known time range string
            stats [today|yesterday|lastweek|thisweek]
            
            # From an absolute date/time point:
            stats from 8:00
            stats from 2010-04-10_8:00

            # From a date/time relative to today (beginning of the day)
            stats from [+-][\d+]w[\d+]d

            # From a date/time relative to today (from current time)
            stats from [+-][\d+]w[\d+]d[\d+]h
    
            # From a date/time for a given duration
            stats from [from_expression] for [\d+]w[\d+]d[\d+]h

        '''
        ret = self.cmd_parser.parse_cmd("stats", args.split(" "))
        self.print_output(ret)

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

        Possible usage:

            # Change project attribution for a given record. (Record id is show by the show command)
            edit id <record_id> project <project_name>

            # Change record start date/time with absolute date/time
            edit id <record_id> from 8:00
            edit id <record_id> from 2010-04-10_8:00

            # Shift record start date/time with relative date/time
            edit id <record_id> from +1h

            # Shift record end date/time with relative date/time
            edit id <record_id> to +1h

            # Shift complete record by 1h
            edit id <record_id> from +1h to +1h

        '''
        ret = self.cmd_parser.parse_cmd("edit", args.split(" "))
        self.print_output(ret)

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

        Possible usage

            # Delete records 1, 2, 3, and 4
            rm 1 2 3 4

        '''
        ret = self.cmd_parser.parse_cmd("rm", args.split(" "))
        self.print_output(ret)

    @typechecked
    def complete_rm(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Autocompletion for the rm command
        '''
        # Not implemented yet
        return self.cmd_parser.delete_actions["id"]["complete"]()

    @typechecked
    def do_show(self, args: cmd2.parsing.Statement) -> None:
        r'''
        Process a show command        

        Possible usage: 

            # Known time range string
            show [today|yesterday|lastweek|thisweek]
            
            # From an absolute date/time point:
            show from 8:00
            show from 2010-04-10_8:00

            # From a date/time relative to today (beginning of the day)
            show from [+-][\d+]w[\d+]d[\d+]h

            # From a date/time relative to today (from current time)
            show from [+-][\d+]w[\d+]d[\d+]h exact

            # From a date/time for a given duration
            show from [from_expression] for [\d+]w[\d+]d[\d+]h

        '''
        #print("Executing: show {}".format(args))
        ret = self.cmd_parser.parse_cmd("show",  args.split(" "))
        self.print_output(ret)

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
        Process a work command.

        Creates a new work record. That record can be either opened (in progress) or
        closed if a duration (argument `for`) was provided.

        When creating a record, the following arguments can be provided:
        - on <project_name>, the project being worked on.
        - for <duration> the duration of the record. This closes the report.
        - at <date/time> the start time of the record.

        If a record is opened (no end date/time), it will be closed automatically when a new
        work entry is added.
        Otherwise, a work record can be closed using `work done`.

        Possible usage:
            # Work on something, but project is unknown right now (ie arrived at work)
            work

            # This must be terminated by specifying the project on which one worked using:
            work done on <project_name>

            # Extra arguments for work (all optionals):
            work on <project_name> at <date/time> for <duration> 
            # Example:
            work on Project1 at 8:00 for 1h



        '''

        #print("Executing: work: {}".format(args))
        ret = self.cmd_parser.parse_cmd("work",  args.split(" "))
        self.print_output(ret)

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


        # Complete values for option "on", "for" etc. from database
        #self.poutput("Last option: {}, begidx: {}, endidx: {}".format(last_option, begidx, endidx))
        if last_option in self.cmd_parser.work_actions and self.cmd_parser.work_actions[last_option]["complete"] is not None:
            # Provide options
            all_projects = self.cmd_parser.work_actions[last_option]["complete"]()

            projects = [k for k in all_projects
                        if k.startswith(line[begidx:endidx])]
            return projects


        # Otherwise suggest options
        work_act = Counter(self.cmd_parser.work_actions.keys())
        prev_args = Counter(line.split(" "))
        if prev_args:
            avail_options = list(work_act - prev_args)
            return [k for k in avail_options if k.startswith(line[begidx:endidx])]
        else:
            return self.cmd_parser.work_actions["complete"]

    @typechecked
    def do_project(self, args: cmd2.parsing.Statement) -> None:
        '''
        Execute a project command.

        Allows you to:
        - show the project list,
        - add new projects,
        - delete projects (if not used),
        - rename projects.

        Possible usage:
            # get a list of projects
            project list 
            
            # add a new project
            project add MyProject

            # add a new project as child of another
            project add MyProject.Subproject1

            # rename a project or a subproject (always identified by ID)
            project id <project_id> rename NewProjectName

            # delete a project
            # This is only possible for projects not associated to any records
            project rm <project_id>
        '''
        ret = self.cmd_parser.parse_cmd("project",  args.split(" "))
        self.print_output(ret)

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
    @typechecked
    def do_todo(self, args: cmd2.parsing.Statement) -> None:
        '''
        Execute a todo command.
        '''
        
        ret = self.cmd_parser.parse_cmd("todo",  args.split(" "))
        self.print_output(ret)

    @typechecked
    def complete_todo(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        '''
        Autocompletion for the todo command
        todo list
        todo add <todo> [project] <project_name>
        todo id <todo_id> done
        todo id <todo_id> edit <new descr>
        todo rm <todo_id>
        
        '''

        last_option = self.last_option(line, begidx, endidx)

        # Complete values for option "id", "project", "from", "to" 
        #self.poutput("Last option: {}, begidx: {}, endidx: {}".format(last_option, begidx, endidx))
        if last_option in self.cmd_parser.todo_actions:
            # Provide options
            if self.cmd_parser.todo_actions[last_option]["type"] == ArgType.Final:
                return []
            if not self.cmd_parser.todo_actions[last_option]["complete"]:
                return []
            items = self.cmd_parser.todo_actions[last_option]["complete"]()
            sel_items = [k for k in items
                        if k.startswith(line[begidx:endidx])
                        ]
            return sel_items

        # Otherwise suggest options
        proj_act = Counter(self.cmd_parser.todo_actions.keys())
        prev_args = Counter(line.split(" "))
        #print(prev_args)
        if prev_args:
            avail_options = list(proj_act - prev_args)
            # Exclude actions which have no further argument
            
            return [k for k in avail_options if k.startswith(line[begidx:endidx])]
        else:
            return self.cmd_parser.edit_actions["complete"]
