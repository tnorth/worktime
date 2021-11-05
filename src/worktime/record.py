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

from prettytable import PrettyTable
from typing import (
    List,
)
from cmd2 import (
    ansi,
)
from enum import Enum
import datetime
import copy
import re
import math
from natsort import natsorted, humansorted
from typing import Optional, Tuple, List, Union
from collections.abc import Mapping, Sequence

import worktime.db as db

try:
    from typeguard import typechecked
except ImportError:
    # typechecked is a no-op
    def typechecked(func):
        def inner(*args, **kwargs):
            return func(*args, **kwargs)
        return inner


# Command line arguments may have different types
class ArgType(Enum):
    Time = 1, # Absolute date/time
    Duration = 2, # Duration in week/day/hour
    String = 3, # Some custom variable
    Final = 4, # Not followed by any argument

# Format a work entry.
# NOTE: to improve.
# We assume here records of (record_id, project_id, start_time, end_time, duration)
@typechecked
def format_records(recs: List[Sequence], existing_table: PrettyTable=None) -> PrettyTable:
    if existing_table is not None:
        t = existing_table
    else:
        t = PrettyTable()
        t.field_names =  ("ID", "Project", "Start time", "End time", "Duration")
        t.align["Project"] = "l"
        t.align["Start time"] = "l"
        t.align["End time"] = "l"
        t.align["Duration"] = "l"
        
    for i in recs:
        row = list(i)
        if row[3] == None: # In progress
            row[3] = ansi.style("In progress", fg="red")
            row[4] = ""
        
        t.add_row(row)

    return t

# Format entries: make entry size proportional to the work item duration
# NOTE: this is currently unused
@typechecked
def format_records2(recs: List[List], existing_table: PrettyTable=None) -> PrettyTable:
    if existing_table is not None:
        t = existing_table
    else:
        t = PrettyTable()
        t.field_names =  ("ID", "Project", "Duration")
        t.align["Project"] = "l"
        t.align["Duration"] = "l"
        
    for i in recs:
        end = i[3].strftime("%H:%m") if i[3] else ""
        proj_desc = "{} ({}) -- {})".format(i[1], i[2].strftime("%H:%m"), end)
        duration = int((i[4]).total_seconds() / 3600 * 4) if i[4] else 0
        if duration == 0:
            duration = 1
        proj_desc += "".join(["\n",] * duration)
        row = (i[0], proj_desc, i[4])
        t.add_row(row)

    return t

# Format projects:
# NOTE: to improve
# Assumes (project_id, project_path)
@typechecked
def format_projects(recs: List[dict], proj_flat_list: dict, existing_table: PrettyTable=None) -> PrettyTable:
    if existing_table is not None:
        t = existing_table
    else:
        t = PrettyTable()
        t.field_names =  ("ID", "Project path",)
        t.align["ID"] = "l"
        t.align["Project path"] = "l"

    for i in recs:
        row = (i["pid"], proj_flat_list[i["pid"]])
        t.add_row(row)

    return t

def format_todos(recs: List[dict], existing_table: PrettyTable=None,
                 show=None) -> PrettyTable:

    show_items = {"due": "due_ts", "opened": "open_ts", "closed": "done_ts"}
    extra_items = [show_items[k] for k in show if k in show_items] if show else []

    if existing_table is not None:
        t = existing_table
    else:
        t = PrettyTable()
        field_names =  ["ID", "Descr", "Project"]  + [k.title() for k in show_items.keys() if k in show]
        t.field_names = field_names
        t.align["ID"] = "l"
        t.align["Project path"] = "l"

    for i in recs:
        row = [i["tid"], i["descr"], i["project_name"]] + [datetime.datetime.fromtimestamp(i[k]) if i[k] is not None else "" for k in extra_items]
        t.add_row(list(row))

    return t

def rel_duration_bar(norm_val : float, width : int) -> str:
        partial_progress = (" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉")
        bar_width = int(norm_val * width) # Drop fractional part
        remainder = (norm_val * width - bar_width) * len(partial_progress)
        return "█" * bar_width + partial_progress[int(remainder)]


def do_return(success: bool, output=None, notify=None, warning=None, error=None) -> dict:
    return {"success": success, "output": output, "notify": notify, "warning": warning, "error": error}


# Process commands based on the captured arguments
class CmdParser:
    """
    Provides information about what arguments are available and what their option is.
    Then receives command line arguments, parse them, and execute the associated action.
    """
    @typechecked
    def __init__(self, db: db.RecordDb) -> None:
        # Known commands
        self.cmds = {"work": self.parse_work, "show": self.parse_show, 
                     "edit": self.parse_edit, "rm": self.parse_delete,
                     "stats": self.parse_stats, "project": self.parse_project,
                     "todo": self.parse_todo, }
        # Path to the record database
        self.db = db
        # Actions for the work command
        self.work_actions = {
                "on": { 
                        "complete": self.get_project_list,
                        "type": ArgType.String
                      },
                "at" : {"complete": self.get_time_dummy, 
                        "type": ArgType.Time,
                       },
                "for": {"complete": self.get_duration_dummy,
                        "type": ArgType.Duration
                        },

                "until": {
                        "complete": self.get_time_dummy, 
                        "type": ArgType.Time,
                        },
                "done": {"complete": None,
                         "type": ArgType.Final
                        },
                }
        # Actions for the show command
        self.show_actions = {
                        "today": {"complete": None,
                                  "type": ArgType.Final,
                                },
                        "yesterday":{"complete": None,
                                  "type": ArgType.Final,
                                },
                        "thisweek":{"complete": None,
                                  "type": ArgType.Final,
                                },
                        "lastweek":{"complete": None,
                                  "type": ArgType.Final,
                                },
                        "from": {"complete": self.get_offset_dummy,
                                "type": ArgType.Time,
                                },
                        "for":  {"complete": self.get_duration_dummy,
                                "type": ArgType.Duration,
                                },
                        "until": {
                                "complete": self.get_time_dummy, 
                                "type": ArgType.Time,
                                },
                        "exact": {"complete": None,
                                  "type": ArgType.Final,
                                 }
                        }
        # Actions for the show command
        self.stats_actions = self.show_actions
        # Actions for the rm command
        self.delete_actions = {
            "id": {"complete": self.get_entries_idx,
                   "type": ArgType.String},
            }
        # Actions for the edit command
        self.edit_actions = {
            "id": {"complete": self.get_entries_idx,
                   "type": ArgType.String},
            "project": {"complete": self.get_project_list,
                       "type": ArgType.String },
            "from": {"complete": self.get_time_dummy,
                     "type": ArgType.Time},
            "to": {"complete": self.get_time_dummy,
                     "type": ArgType.Time},
        }
        # Actions for the project command
        self.projects_actions = {
            "id": {"complete": self.get_project_idx,
                   "type": ArgType.String},
            "list": {"complete": None,
                     "type": ArgType.Final,
                    },
            "add" :  {"complete": self.get_project_list,
                       "type": ArgType.String,
                     },
            "rm": {"complete": self.get_project_list,
                       "type": ArgType.String,
                     },
            "rename": {"complete": self.get_project_list,
                       "type": ArgType.String,
                     },
                
            }
        # Todos
        self.todo_actions = {
            "id": {"complete": self.get_todo_idx, "type": ArgType.String},
            "list": {"complete": None, "type": ArgType.Final},
            "opened": {"complete": None, "type": ArgType.Final},
            "closed": {"complete": None, "type": ArgType.Final},
            "dueonly": {"complete": None, "type": ArgType.Final},
            "add": {"complete": None,
                       "type": ArgType.String,
                     },
            "due": {"complete": self.get_time_dummy, "type": ArgType.Time},
            "prio": {"complete": self.get_prio_dummy, "type": ArgType.String},
            "project": {"complete": self.get_project_list,
                       "type": ArgType.String },
            "rm": {"complete": self.get_todo_idx,
                       "type": ArgType.String,
                     },
            "done": {"complete": None, "type": ArgType.Final},
        }


    @typechecked
    def define_prompt(self) -> str:
        ongoing = self.db.get_ongoing_projects()
        unassigned = " [unassigned]" if len(ongoing) > 0 and ongoing[0]["pid"] == 1 else ""
        if len(ongoing) > 0:
            return ansi.style("(wt{}) ".format(unassigned), fg='yellow')
        else:
            return ansi.style("(wt{}) ".format(unassigned), fg='green')

    @typechecked
    def get_project_list(self) -> List[str]:
        '''
        Get a flattened list of project name.
        For instance, project `Bar` being a child of `Foo` will be 
        displayed as  `Foo.Bar`
        '''
        _, _, _, flist = self.db.get_project_tree()
        return list(flist.keys())

    @typechecked
    def get_time_dummy(self) -> List[str]:
        '''
        Provide autocompletion hint for a time argument type
        '''
        return ["now", "8:00", "2020-04-09_09:10"]

    @typechecked
    def get_duration_dummy(self) -> List[str]:
        '''
        Provide autocompletion hint for a duration argument type
        '''
        return ["2h", "7d", "1w"]

    @typechecked
    def get_offset_dummy(self) -> List[str]:
        '''
        Provide autocompletion hint for an offset argument type
        '''
        return ["-1h", "+1h", "+1w1d2h", "-1w", "-3d"]


    @typechecked
    def get_entries_idx(self) -> List[str]:
        '''
        Get the IDs of the last 20 work records
        '''
        last_items = self.db.get_last_records(num=20)
        ids = [str(k["rid"]) for k in last_items]
        return ids

    @typechecked
    def get_project_idx(self) -> List[str]:
        '''
        Return list of all project Ids
        '''
        projects = self.db.get_projects()
        return [str(k["pid"]) for k in projects]


    def get_todo_idx(self) -> List[str]:
        '''
        Return list of all todos Ids
        '''
        todos = self.db.get_todos()
        return [str(k["tid"]) for k in todos]

    def get_prio_dummy(self) -> List[str]:
        return [str(k) for k in range(5)]

    @typechecked
    def split_weekdayhour(self, offset: str) -> List[Optional[int]]:
        '''
        Transform a string of weeks, days, hours into 
        a tuple.
        Example: 1w3d5h => (1, 3, 5)
        Unspecified items are set to known:
        Example: 1w5h => (1, None, 5)
        '''
        # Handle week/day/hour

        mm = re.match(r"(?:([\d\.]+)w)?(?:([\d\.]+)d)?(?:([\d\.]+)h)?(?:([\d\.]+)m)?(?:([\d\.]+)s)?", offset)
        return [int(k) if k else None for k in mm.groups()]

    @typechecked
    def split_duration(self, duration:str) -> Optional[List[Optional[int]]]:
        '''
        Transform a string specifying a duration in hour/min/seconds
        into a tuple.
        Example: 2h30m5s = (2, 30, 5)
        Unspecified items are set to None:
        Example: 5s => (None, None, 5)
        If no hour, minute, or second is specified, returns None.
        '''

        if not ('h' in duration or 'm' in duration or 's' in duration):
            return None

        # Handle h/m/s
        mm = re.match(r"^(?:([\d\.]+)h)?(?:([\d\.]+)m)?(?:([\d\.]+)s)?$", duration)
        return [int(k) if k else None for k in mm.groups()]
    
    @typechecked
    def parse_offset(self, offset: str) -> Tuple[datetime.timedelta, bool]:
        '''
        Transforms a time offset specified as:
          +1[w|d|h]
          (week, day, hour)
        into a timedelta object, plus a boolean indicating whether the given time offset
        has hour resolution

        '''
        wds_offset = [datetime.timedelta(weeks=1),
                      datetime.timedelta(days=1), 
                      datetime.timedelta(hours=1),
                      datetime.timedelta(minutes=1),
                      datetime.timedelta(seconds=1)]
                          
        sign = -1 if offset.startswith("-") else 1
        if offset[0] == '-' or offset[0] == '+':
            offset = offset[1:]

        offsets = [n * f \
                    for n, f in zip(self.split_weekdayhour(offset), wds_offset) \
                    if n is not None]
        offset_vals = sum(offsets, start=datetime.timedelta(seconds=0))
        return sign * offset_vals, 'h' in offset

    @typechecked
    def parse_duration(self, duration: str) -> Tuple[Optional[datetime.timedelta], str]:
        '''
        Transform a duration specified as either:
        - a time duration in hours/minutes/seconds
            OR
        - a time duration in week/day/hour
        into a timedelta object.

        Possible inputs: 1w3d, 10:20, 2h

        Warning: it is assumed that seconds are normally omitted:
        ie : 1:20 == 1h20 and not 1m20s
        '''
        if duration.startswith('-'):
            return None, "Invalid duration: can't be negative"
        # check if we have received week/day 
        if 'w' in duration or 'd' in duration:
            parse_duration, _ = self.parse_offset(duration)
            return parse_duration, ""

        # convert format 1:20:30 to 1h20m30s
        if ":" in duration:
            dd = duration.split(":")
            if len(dd) == 2: # we have only hh:mm
                duration = "{}h{}m".format(*dd)
            elif len(dd) == 3: # we have hh:mm:ss
                duration = "{}h{}m{}s".format(*dd)
            else:
                return None, "Unknown duration {}".format(duration)

        hms = self.split_duration(duration)
        if hms is None:
            return None, "Invalid duration '{}'".format(duration)
        hms_flt = [float(k) if k is not None else 0 for k in hms]
        sec_mult = (3600, 60, 1)
        time_sec = sum([k * m for k, m in zip(hms_flt, sec_mult)])
        return datetime.timedelta(seconds=time_sec), ""

    @typechecked
    def parse_time(self, time: str) -> Union[datetime.datetime, datetime.timedelta]:
        '''
        Transform a given time string into a datetime object.


        
        Absolute time: 
            yyyy/mm/dd_hh:mm:ss (with optionals)
            hh:mm:ss
            etc.

        Relative time:
            if prefixed with + or -

        Shortcuts:
            now
        '''

        def parse_hms(time_str):
            '''return corresponding timedelta'''
            d = datetime.time.fromisoformat(time_str)
            return d

        def parse_date(date_str):
            '''return corresponding date'''
            return datetime.date.fromisoformat(date_str)

        if time.startswith("-") or time.startswith("+"):
            # relative time provided
            offset, _ = self.parse_offset(time)
            return offset

        if time == "now":
            return datetime.datetime.now()
        
        if "_" in time:
            date, hour = time.split("_")
            # Day defined
            date = parse_date(date)
            # Time defined
            # Workaround to make h:mm a valid iso time
            if len(hour.split(":")[0]) < 2:
                hour = "0" + hour
            hour = parse_hms(hour)
            return datetime.datetime.combine(date, hour)
        elif "-" in time:
            # Only a date
            return self.date2dt(parse_date(time))
        elif ":" in time:
            # Workaround to make h:mm a valid iso time
            if len(time.split(":")[0]) < 2:
                time = "0" + time
            # Only a time
            #print("returing: ", datetime.datetime.combine(datetime.datetime.now(), parse_hms(time)))
            return datetime.datetime.combine(datetime.datetime.now(), parse_hms(time))
        elif 'h' in time or 'm' in time or 's' in time:
            duration = self.split_duration(time)
            if duration is None:
                raise("Unknown time format {}".format(time))
            hms = ":".join([str(k) if k else '00' for k in duration])
            hms = datetime.time.fromisoformat(hms)
            return datetime.datetime.combine(datetime.datetime.now(), hms)
        else:
            raise("Unknown date format")

    @typechecked
    def interpret_args(self, args: List[str], actions: dict) -> Tuple[bool, dict, str]:
        '''
        Parse command line arguments to interpret argument values
        based on their expected types
        Returns a tuple (True|False, dictionary of arguments, message)
        describing whether the parsing succeeded, the arguments, and 
        an associated message.

        NOTE: the argument order is lost. It is assumed that
        argument pairs are a sufficient information.
        '''
        args_r = args.copy()
        proc_args = {}
        if args_r[0] == '': return True, {}, ""
        while True:
            option = args_r[0]
            if option in actions:
                if actions[option]["type"] == ArgType.Final:
                    # not intended to be followed
                    # Do something
                    #print("Processing {} without value".format(option))
                    proc_args[option] = None
                    args_r = args_r[1:] if len(args_r) > 1 else []
                else:
                    # take some argument
                    if len(args_r) < 2:
                        return False, {}, "Error: option {} must have a value".format(option)
                       
                    val = args_r[1]
                    # print("Processing {} with val {}".format(option, val))

                    if actions[option]["type"] == ArgType.Time:
                        abs_time = self.parse_time(val)
                        #print("Got time: {}".format(abs_time))

                        proc_args[option] = abs_time

                    elif actions[option]["type"] == ArgType.Duration:
                        rel_time, msg = self.parse_duration(val)
                        if rel_time is None:
                            return False, {}, msg
                        #print("Got rel time: {}".format(rel_time))
                        proc_args[option] = rel_time

                    else:
                        proc_args[option] = val

                    args_r = args_r[2:] if len(args_r) > 2 else []


                if args_r == []:
                    break

            else:
                return False, {}, "Error: invalid option {}".format(option)

        return True, proc_args, ""

    @staticmethod
    @typechecked
    def find_end_time(args: dict, start_time: datetime.datetime) -> Tuple[bool, Optional[Union[str, datetime.datetime, datetime.timedelta]]]:
            if not "for" in args and not "until" in args:
                return True, None
            if "for" in args and "until" in args:
                return False, "Error: please specify either `for` or `until`, but not both"
            if "for" in args:
                # Use previous start value
                end_time = start_time + args["for"]
            elif "until" in args:
                end_time = args["until"]
            return True, end_time

    @typechecked
    def parse_work(self, args: List[str]) -> dict:
        '''
        Parse provided work command, and execute it.
        Returns: an information message
        '''
        ret, proc_args, msg = self.interpret_args(args, self.work_actions)
        if not ret:
            return do_return(success=False, error=msg)

        _, _, projs_by_id, proj_id = self.db.get_project_tree()

        if not "on" in proc_args:
            # Assign to special project "Not assigned"
            project_id = 1
            project_name = projs_by_id[1]
        else:
            project_name = proc_args["on"]
            if project_name in proj_id:
                project_id = proj_id[project_name]
            else:
                return do_return(success=False, error="Unknown project: '{}'".format(proc_args["on"]))


        # If done is included, every other argument refers to the previous ongoing entry
        # if any.
        # In absence of "done", a new entry will be created, and ongoing entries will be terminated.
        ongoing_projects = self.db.get_ongoing_projects()
        if "done" in proc_args:
            msg = []
            warning = []

            for ongoing_project in ongoing_projects:
                idx = ongoing_project["rid"]

                # done at ... : at represents the end date (start is already set)
                # done for ... : for represents the duration of the previous task
                # at and for are mutually exclusive
                if "at" in proc_args and ("for" in proc_args or "until" in proc_args):
                    msg.append("When finishing an ongoing task, use either 'at' or 'for', not both." +\
                               "\n`work done at` => determines the end time of the ongoing entry" + \
                               "\n`work done for` => determines the duration of the ongoing entry")
                    break
                if "at" in proc_args:
                    if isinstance(proc_args["at"], datetime.timedelta):
                        end_time = datetime.datetime.now() + proc_args["at"]
                    else:
                        end_time = proc_args["at"]
                else:
                    end_time = datetime.datetime.now()

                ret, given_end_time_or_msg = self.find_end_time(proc_args, datetime.datetime.fromtimestamp(ongoing_project["start"]))
                if ret:
                    if given_end_time_or_msg:
                        if isinstance(given_end_time_or_msg, datetime.timedelta):
                            end_time = datetime.datetime.now() + given_end_time_or_msg
                        else:
                            end_time = given_end_time_or_msg
                else:
                    return do_return(success=False, error=given_end_time_or_msg)
                   
                if project_id == 1:
                    # Update project assignation
                    project_id = None

                # Check if the project is assigned
                if ongoing_project["pid"] == 1:
                    # Not assigned
                    
                    warning.append("Warning: completed record {} is not assigned to any project! Use `edit <record_id> project <project_name>` to provide a project name".format(idx))

                msg.append("Updated ongoing record {}".format(idx))
                self.db.update_record(idx, new_end=end_time, new_project_id=project_id)
                msg.append(format_records(self.db.get_records_by_id([idx, ], format=True)).get_string())

                return do_return(success=True, notify="\n".join(msg), warning="\n".join(warning))
            else:
                # Nothing to close
                return do_return(success=False, error="No ongoing project to terminate")
        else:
            # Close ongoing project without changing anything else.
            # Also add a new project based on the provided arguments
            pass

        if not "at" in proc_args:
            # No start specified => use now
            start_time = datetime.datetime.now()
        else:
            if isinstance(proc_args["at"], datetime.timedelta):
                start_time = datetime.datetime.now() + proc_args["at"]
            else:
                start_time = proc_args["at"]

        # No duration specified => task open
        end_time = None
        ret, given_end_time_or_msg = self.find_end_time(proc_args, start_time)
        if ret:
            if given_end_time_or_msg:
                if isinstance(given_end_time_or_msg, datetime.timedelta):
                    end_time = datetime.datetime.now() + given_end_time_or_msg
                else:
                    end_time = given_end_time_or_msg
        else:
            return do_return(success=False, error=given_end_time_or_msg)
        ## Check if there is an overlap with a *finished* working entry
        # print("Start time is: {}".format(start_time))
        ## TODO: refactor this
        start_overlap = self.db.get_overlapping_records(start_time, format=False)
        end_overlap = self.db.get_overlapping_records(end_time, format=False)
        has_overlap = len(start_overlap) > 0 or len(end_overlap) > 0
        idx = [k["rid"] for k in start_overlap] + [k["rid"] for k in end_overlap]
        if has_overlap:
            overlaps = self.db.get_overlapping_records(start_time) + self.db.get_overlapping_records(end_time)
            msg = 'Inserted new record'
            # check if there is an overlap
            # Close them
            self.db.update_records_end(idx, start_time)

            # Notify if an updated (closed) record wasn't assigned to a project
            msg = None
            non_assigned_idx = [k["rid"] for k in self.db.get_records_by_id(idx) if k["pid"] == 1]
            if len(non_assigned_idx) > 0:
                msg = ansi.style("Warning: record {} was not attributed to a project!" \
                        "Use `edit <record_id> project <project_name>` to provide a project name"\
                        .format(", ".join([str(k) for k in non_assigned_idx])), fg='yellow')
            
            # Add the new task
            _ = self.db.insert_record(project_id, start_time, end_time)

            ret = "Closed overlapping ongoing task which was: {}\n".format(", ".join([str(k) for k in idx])) \
                    + format_records(overlaps).get_string() + "\n"\
                    + ansi.style("\nInserted new record for project {} from {} to {}"\
                                    .format(project_name, start_time, end_time), fg='green')
            ret = ret + "\n" + msg if msg else ret
            return do_return(success=True, notify=ret)

        else:
            # Normal insertion
            _ = self.db.insert_record(project_id, start_time, end_time)
            return do_return(success=True, notify="Inserted new record for project {} from {} to {}"\
                                .format(project_name, start_time, end_time))
    
    @staticmethod
    @typechecked
    def date2dt(x: datetime.datetime.date) -> datetime.datetime:
        '''Make a datetime object based on a given date'''
        return datetime.datetime.combine(x, datetime.time.min)

    @typechecked
    def shortcut_to_dates(self, args: dict) -> Tuple[Optional[datetime.datetime], Optional[datetime.datetime]]:
        '''
        Transform common names to a time tuple.
        '''
        today = self.date2dt(datetime.date.today())
        start_date = None
        end_date = None

        if 'today' in args:
            start_date = today
            end_date = today + datetime.timedelta(days=1)
        if 'yesterday' in args:
            start_date = today + datetime.timedelta(days=-1)
            end_date = today
        elif 'lastweek' in args:
            start_date = today + datetime.timedelta(days=-datetime.date.today().weekday(), weeks=-1)
            end_date = start_date + datetime.timedelta(days=5)
        elif 'thisweek' in args:
            start_date = today + datetime.timedelta(days=-datetime.date.today().weekday(), weeks=0)
            end_date = start_date + datetime.timedelta(days=5)
       
        return start_date, end_date

    @typechecked
    def parse_show(self, args: List[str]) -> dict:
        '''
        Parse provided show command, and execute it.
        Returns: an information message
        
        Known format:
        show today
        show yesterday 
        show thisweek
        show lastweek
        show from [+1[w|d|h] for [1d]
        show week [week number]
        '''

        ret, proc_args, msg = self.interpret_args(args, self.show_actions)
        if not ret:
            return do_return(success=False, error=msg)

        today = self.date2dt(datetime.date.today())
        _, _, id_to_proj, _ = self.db.get_project_tree()

        # Convert short project name to project full path
        def rep_with_proj_tree(recs):
            # first is assumed to be record ID, 
            # second to be the project ID
            up_recs = []
            for rec in recs:
                up_recs.append([rec[0], id_to_proj[rec[1]], ] + list(rec[2:]))
            return up_recs    

        # default to week view
        if proc_args == {}:
            proc_args = {'thisweek': None}
        start_date, end_date = self.shortcut_to_dates(proc_args)
        if start_date is None or end_date is None:
            if "from" in proc_args:
                if "exact" in proc_args:
                    if isinstance(proc_args["from"], datetime.timedelta):
                        # It's relative to exactly now()
                        start_date = datetime.datetime.now() + proc_args["from"]
                    else:
                        start_date = proc_args["from"]
                else:
                    # It's relative to the start of the day
                    if isinstance(proc_args["from"], datetime.timedelta):
                        # It's relative to exactly now()
                        start_date = today + proc_args["from"]
                    else:
                        start_date = proc_args["from"]

                end_date = today + datetime.timedelta(days=1)   

            ret, given_end_time_or_msg = self.find_end_time(proc_args, start_date)
            if ret:
                if given_end_time_or_msg:
                    if isinstance(given_end_time_or_msg, datetime.timedelta):
                        end_date = today + given_end_time_or_msg
                    else:
                        end_date = given_end_time_or_msg
            else:
                return do_return(success=False, error=given_end_time_or_msg)
        
        items = self.db.get_records(start_date, end_date)
        items = rep_with_proj_tree(items)
        ret = "Showing from {} to {}".format(start_date, end_date) + "\n"
        ret += format_records(items).get_string()
        return do_return(success=True, output=ret)
    
    @typechecked
    def parse_stats(self, args: List[str]) -> dict:
        '''
        Parse provided stats command, and execute it.
        Returns: an information message
        
        Known format: see parse_show
        '''
        ret, proc_args, msg = self.interpret_args(args, self.stats_actions)
        if not ret:
            return do_return(success=False, error=ret)
        # Get projects list
        tree_s, tree_t, flat_tree, flat_tree_rev = self.db.get_project_tree()
        
        today = self.date2dt(datetime.date.today())

        # default to week view
        if proc_args == {}:
            proc_args = {'thisweek': None}
        start_date, end_date = self.shortcut_to_dates(proc_args)
        if start_date is None or end_date is None:
            if "from" in proc_args:
                if "exact" in proc_args:
                    if isinstance(proc_args["from"], datetime.timedelta):
                        # It's relative to exactly now()
                        start_date = datetime.datetime.now() + proc_args["from"]
                    else:
                        start_date = proc_args["from"]
                else:
                    # It's relative to the start of the day
                    if isinstance(proc_args["from"], datetime.timedelta):
                        # It's relative to exactly now()
                        start_date = today + proc_args["from"]
                    else:
                        start_date = proc_args["from"]

                end_date = today + datetime.timedelta(days=1)   
            if "for" in proc_args:
                end_date = start_date + proc_args["for"]

        items = self.db.get_period_stats(start_date, end_date)

        t = PrettyTable()
        t.field_names = ("Project ID", "Project", "Time spent", "Graph")
        t.align["Project"] = "l"
        t.align["Time spent"] = "l"
        t.align["Graph"] = "l"

        data = []
        # Total time spent
        tot_duration = sum([k["duration"] for k in items])

        # Stats per project
        for proj_idx, _ in tree_s.items():
            proj_children_recursive = self.db.get_children_list(tree_s, proj_idx)
            duration = 0
            is_sum_res = False
            for item in items:
                if item["pid"] == proj_idx:
                    # print("Adding time for {} = {}".format(item[1], datetime.timedelta(seconds=item[2])))
                    duration += item["duration"]
            for item in items:
                if item["pid"] in proj_children_recursive:
                    is_sum_res = True
                    # print("Adding time for child {} = {}".format(item[1], datetime.timedelta(seconds=item[2])))
                    duration += item["duration"]
            
            proj_name = flat_tree[proj_idx]
            if duration > 0:
                # use https://mike42.me/blog/2018-06-make-better-cli-progress-bars-with-unicode-block-characters
                data.append([proj_idx, proj_name, 
                             "{:.2f}".format(duration / 3600.) + " h",
                             rel_duration_bar(duration/tot_duration, 30), is_sum_res] )

        # Sort by project name
        data = natsorted(data, key=lambda x: x[1])

        # Color
        for k, item in enumerate(data):
            # Check if item[1] has a parent
            if tree_s[item[0]]["parent"] is None:
                data[k][1] = ansi.style(data[k][1], fg='green')
            else:
                subprojs = data[k][1].split(".")
                subproj = subprojs[-1]
                subproj = (len(data[k][1]) - len(subproj) - len(subprojs)) * " " + "└─" + subproj
                data[k][1] = subproj
            if data[k][-1]:
                data[k][2] = ansi.style(data[k][2], fg='yellow')

        for k in data:
            t.add_row(k[:-1])

        t.add_row(("Total", "[All projects]", "{:.2f} h".format(tot_duration / 3600.), str(datetime.timedelta(seconds=tot_duration))))        
        ret = "Stats from {} to {}".format(start_date, end_date) + "\n"

        return do_return(success=True, output=ret + t.get_string())

    @typechecked
    def parse_edit(self, args: List[str]) -> dict:
        '''
        Parse provided edit command, and execute it.
        Returns: an information message

        Known format:
        edit id <record> [project <project_name>] [from <start time>] [to <end time>]

        Example:
        edit id 10 project MyProject from 10:00 to 11h
        '''

        ret, proc_args, msg = self.interpret_args(args, self.edit_actions)
        if not ret:
            return do_return(success=False, error=msg)
        edit_id = None
        project_id = None
        new_start_time = None
        new_end_time = None
        if not "id" in proc_args:
            return do_return(success=False, error="Required parameter `id` is missing.")
        else:
            edit_id = int(proc_args["id"])
        
        if "project" in proc_args:
            # Re-assign to a different project
            _, _, _, proj_to_id = self.db.get_project_tree()
            if proc_args["project"] in proj_to_id:
                project_id = proj_to_id[proc_args["project"]]
            else:
                return do_return(success=False, error="Invalid project: {}".format(proc_args["project"]))

        if "from" in proc_args:
            # Edit start time
            if isinstance(proc_args["from"], datetime.timedelta):
                # Shift the existing start date by this amount
                # required getting it first
                edit_item = self.db.get_records_by_id([edit_id, ])
                curr_start = datetime.datetime.fromtimestamp(edit_item[0][3])
                new_start_time = curr_start + proc_args["from"]
            else:
                new_start_time = proc_args["from"]

        if "to" in proc_args:
            # Edit end time
            if isinstance(proc_args["to"], datetime.timedelta):
                edit_item = self.db.get_records_by_id([edit_id, ])
                curr_end = datetime.datetime.fromtimestamp(edit_item[0][4])
                new_end_time = curr_end + proc_args["to"]
            else:
                new_end_time = proc_args["to"]

        if "from" in proc_args or "to" in proc_args:
            # Check overlaps
            start_overlap = self.db.get_overlapping_records(new_start_time) if new_start_time is not None else []
            end_overlap = self.db.get_overlapping_records(new_end_time) if new_end_time is not None else []
            # Ignore this item
            start_overlap = [k for k in start_overlap if k[0] != edit_id]
            end_overlap = [k for k in end_overlap if k[0] != edit_id]

            if len(start_overlap) > 0:
                msg = "Cancelling: Records overlap new start time ({}):\n".format(new_start_time)
                return do_return(success=False, error=msg + format_records(start_overlap).get_string())

            if len(end_overlap) > 0:
                msg = "Cancelling: Records overlap new end time ({}):\n"
                return do_return(success=False, error=msg + format_records(end_overlap).get_string())
            
        # Update
        self.db.update_record(edit_id, new_start=new_start_time, new_end=new_end_time, new_project_id=project_id)
        return do_return(success=True, notify="Updated record {}".format(edit_id))
    
    @typechecked
    def parse_delete(self, args: List[str]) -> dict:
        '''
        Parse provided delete command, and execute it.
        Returns: an information message

        Example:
        rm id <record_id>
        '''
        
        # Only retrieve IDs
        if len(args) == 0:
            return do_return(success=False, error="Error: no record ID provided")
        ids = [int(k) for k in args] # Ensure only integers are taken
        deleted_ids = self.db.delete_records(ids)
        return do_return(success=True, notify="Records deleted : {}".format(", ".join([str(k) for k in deleted_ids])))


    @typechecked
    def parse_project(self, args: List[str]) -> dict:
        '''
        Parse provided project command, and execute it.
        Returns: an information message
        
        See and edit projects
            # Show all projects
            project list
            # Add a project
            project add <project path> # Add some project as child of something.
            # Rename a project
            project id <project id> rename <subproject name>
            # TODO
            project hide <project_id> # Hides a project and its children

            Do we want these ones?
            project rm <project id> # Delete a project. Warning! only if unused!
        '''

        ret, proc_args, msg = self.interpret_args(args, self.projects_actions)
        if not ret:
            return do_return(success=False, error=msg)

        tree_s, _, proj_byids, projs_byname = self.db.get_project_tree()

        if len(proc_args) == 0:
            # No args
            proc_args = {'list':None}

        if 'list' in proc_args:
            proj_list = self.db.get_projects()
            proj_names = format_projects(proj_list, proj_byids)
            return do_return(success=True, output=proj_names.get_string())
        elif 'add' in proc_args:
            new_project_path = proc_args['add'].split(".")
            new_project_name = new_project_path[-1]
            
            # check if we already have this project
            if proc_args['add'] in projs_byname:
                return do_return(success=False, error="Project already exists")
            # check if the new project is the child of some other project
            parent_id = None
            if len(new_project_path) > 1:
                project_basepath = ".".join(new_project_path[:-1])
                if project_basepath in proj_byids.values():
                    # get the ID of the parent
                    parent_id = projs_byname[project_basepath]
            self.db.insert_project(new_project_name, parent_id=parent_id)
            return do_return(success=True, notify="Added project {}".format(new_project_name))

        elif 'rm' in proc_args:
            # NOTE: dangerous operation. What about children?
            # 1) check if the project has children and if any record using
            # one of these children is present. If not, delete.
            project_name = proc_args['rm']
            project_id = projs_byname[project_name]
            if project_id == 1:
                # Don't allow deletion of this special project
                return do_return(success=False, error="Can't delete special project 'Not assigned'")
            children_list = self.db.get_children_list(tree_s, project_id)
            recs = self.db.get_records_for_projects(children_list + [project_id, ])
            if len(recs) > 0:
                return do_return(success=False, error="Can't delete project {}: used by records: \n".format(project_id) + \
                     ", ".join([str(k["pid"]) for k in recs]))
            
            else:
                self.db.delete_project(project_id)
                return do_return(success=True, notify="Deleted project {}".format(project_id))

        elif 'id' in proc_args:
            if 'rename' in proc_args:
                new_name = proc_args["rename"]
                project_id = int(proc_args['id'])
                if "." in new_name:
                    return do_return(success=False, error="Can't change project path. Please rename parent project first.")
                if not self.db.rename_project(project_id, new_name):
                    return do_return(success=False, error="Project ID {} doesn't exist.".format(proc_args['id']))
                else:
                    ret = "Updated project ID {}".format(proc_args['id'])
                    proj = self.db.get_project_id(project_id)
                    return do_return(success=True, notify=ret + "\n" + format_projects(proj, proj_byids).get_string())
            else:
                # Just show it
                proj = self.db.get_project_id(project_id)
                return do_return(success=True, output=format_projects(proj, proj_byids).get_string())

    @typechecked
    def parse_todo(self, args: List[str]) -> dict:
        '''
        Parse provided todo command, and execute it.
        Returns: an information message
        
        See and edit projects
            # Show all todos
            todo list
            # Add a todo
            todo add <descr> 
            ...
            TODO
        '''
        ret, proc_args, msg = self.interpret_args(args, self.todo_actions)
        if not ret:
            return do_return(success=False, error=msg)

        tree_s, _, proj_byids, projs_byname = self.db.get_project_tree()

        if len(proc_args) == 0:
            # No args
            proc_args = {'list':None}

        if 'list' in proc_args:
            todo_list = format_todos(self.db.get_todos(opened_only=True), show=('due', 'opened'))
            return do_return(success=True, output=todo_list.get_string())

        if 'opened' in proc_args:
            todo_list = format_todos(self.db.get_todos(opened_only=True), show=('due', 'opened'))
            return do_return(success=True, output=todo_list.get_string())
        if 'closed' in proc_args:
            todo_list = format_todos(self.db.get_todos(closed_only=True), show=('due', 'opened', 'closed'))
            return do_return(success=True, output=todo_list.get_string())

        if 'dueonly' in proc_args:
            todo_list = format_todos(self.db.get_todos(closed_only=False, opened_only=True, due_only=True), show=('due', 'opened'))
            return do_return(success=True, output=todo_list.get_string())

        elif 'add' in proc_args:
            due_time = None
            project_id = None
            priority = None
            if 'due' in proc_args:
                if isinstance(proc_args["due"], datetime.timedelta):
                    due_time = datetime.datetime.now() + proc_args["due"]
                else:
                    due_time = proc_args["due"]

            if 'project' in proc_args:
                if proc_args['project'] in projs_byname:
                    project_id = projs_byname[proc_args['project']]
                else:
                    return do_return(success=False, error="Unknown project: '{}'".format(proc_args["project"]))

            if 'prio' in proc_args:
                try:
                    priority = int(proc_args['prio'])
                except:
                    return do_return(success=False, error="Invalid priority: '{}'".format(proc_args["prio"]))

            self.db.insert_todo(proc_args["add"], project_idx=project_id, due=due_time, priority=priority)

            return do_return(success=True, notify="Added ToDo")

        elif 'rm' in proc_args:
            ids = proc_args['rm']
            recs = self.db.delete_todos([int(ids),])
            return do_return(success=True, notify="Deleted item:\n{}".format(format_todos(recs, show=('due', 'opened', 'closed'))))

        elif 'id' in proc_args:
            try:
                id_ = int(proc_args["id"])
            except:
                return do_return(success=False, error="Invalid id '{}'".format(proc_args['id']))
            if 'edit' in proc_args:
                pass
            elif 'done' in proc_args:
                recs = self.db.close_todo(id_, done_ts=datetime.datetime.now())
                if len(recs) == 1:
                    return do_return(success=True, notify="Closed item:\n{}".format(format_todos(recs, show=('due', 'opened', 'closed'))))
            elif 'project' in proc_args:
                if proc_args['project'] in projs_byname:
                    project_id = projs_byname[proc_args['project']]
                else:
                    return do_return(success=False, error="Unknown project: '{}'".format(proc_args["project"]))
                recs = self.db.update_todo_project(id_, project_id=project_id)
                if len(recs) == 1:
                    return do_return(success=True, notify="Updated todo was:\n{}".format(format_todos(recs, show=('due', 'opened', 'closed'))))
            else:
                pass



    @typechecked
    def parse_cmd(self, cmd: str, args: List[str]) -> dict:
        '''
        Execute the appropriate parse function
        '''
        quote_start = -1
        quote_end = -1
        searching = False
        new_args = []
        for i, k in enumerate(args):
            if k.startswith("\""):
                if not searching:
                    quote_start = i
                    searching = True
            if k.endswith("\""):
                quote_end = i
                if searching:
                    new_args.append((" ".join(args[quote_start:quote_end + 1]))[1:-1])
                    searching = False
            else:
                if not searching:
                    new_args.append(k)

        #print(args)
        #print(new_args)

        return self.cmds[cmd](new_args)
        

if __name__ == '__main__':
    pass