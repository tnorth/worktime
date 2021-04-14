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
from natsort import natsorted, humansorted

import worktime.db

# Command line arguments may have different types
class ArgType(Enum):
    Time = 1, # Absolute date/time
    Duration = 2, # Duration in week/day/hour
    Offset = 3, # Time offset ie +1h, -1d
    String = 4, # Some custom variable
    Final = 5, # Not followed by any argument

# Format a work entry.
# NOTE: to improve.
# We assume here records of (record_id, project_id, start_time, end_time, duration)
def format_records(recs, existing_table=None):
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
def format_records2(recs, existing_table=None):
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
def format_projects(recs, proj_flat_list, existing_table=None):
    if existing_table is not None:
        t = existing_table
    else:
        t = PrettyTable()
        t.field_names =  ("ID", "Project path",)
        t.align["ID"] = "l"
        t.align["Project path"] = "l"

    for i in recs:
        row = (i[0], proj_flat_list[i[0]])
        t.add_row(row)

    return t

# Process commands based on the captured arguments
class CmdParser:
    """
    Provides information about what arguments are available and what their option is.
    Then receives command line arguments, parse them, and execute the associated action.
    """
    def __init__(self, db):
        # Known commands
        self.cmds = {"work": self.parse_work, "show": self.parse_show, 
                     "edit": self.parse_edit, "rm": self.parse_delete,
                     "stats": self.parse_stats, "project": self.parse_project}
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
                "done": {"complete": None,
                         "type": ArgType.Final
                        },
                "force": {"complete": None,
                          "type": ArgType.Final
                         }

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
                                "type": ArgType.Offset,
                                },
                        "for":  {"complete": self.get_duration_dummy,
                                "type": ArgType.Duration,
                                },
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

    def get_project_list(self):
        '''
        Get a flattened list of project name.
        For instance, project `Bar` being a child of `Foo` will be 
        displayed as  `Foo.Bar`
        '''
        _, _, _, flist = self.db.get_project_tree()
        return flist.keys()

    def get_time_dummy(self):
        '''
        Provide autocompletion hint for a time argument type
        '''
        return ("now", "8:00", "2020-04-09_09:10")

    def get_duration_dummy(self):
        '''
        Provide autocompletion hint for a duration argument type
        '''
        return ("2h", "1m", "7d", "1w")

    def get_offset_dummy(self):
        '''
        Provide autocompletion hint for an offset argument type
        '''
        return ("-1h", "+1h", "+1w1d2h", "-1w", "-3d")

    def get_entries_idx(self):
        '''
        Get the IDs of the last 20 work records
        '''
        last_items = self.db.get_last_records(num=20)
        ids = [str(k[0]) for k in last_items]
        return ids

    def get_project_idx(self):
        '''
        Return list of all project Ids
        '''
        projects = self.db.get_projects()
        return [str(k[0]) for k in projects]

    def split_weekdayhour(self, offset):
        '''
        Transform a string of weeks, days, hours into 
        a tuple.
        Example: 1w3d5h => (1, 3, 5)
        Unspecified items are set to known:
        Example: 1w5h => (1, None, 5)
        '''
        # Handle week/day/hour

        mm = re.match(r"(?:([\d\.]+)w)?(?:([\d\.]+)d)?(?:([\d\.]+)h)?", offset)
        return [int(k) if k else None for k in mm.groups()]

    def split_duration(self, duration):
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
        mm = re.match(r"(?:([\d\.]+)h)?(?:([\d\.]+)m)?(?:([\d\.]+)s)?", duration)
        return [k if k else None for k in mm.groups()]
    
    def parse_offset(self, offset):
        '''
        Transforms a time offset specified as:
          +1[w|d|h]
          (week, day, hour)
        into a timedelta object.
        '''
        wds_offset = [datetime.timedelta(weeks=1),
                      datetime.timedelta(days=1), 
                      datetime.timedelta(hours=1)]
                          
        sign = -1 if offset.startswith("-") else 1
        if offset[0] == '-' or offset[0] == '+':
            offset = offset[1:]

        offsets = [n * f \
                    for n, f in zip(self.split_weekdayhour(offset), wds_offset) \
                    if n is not None]
        offset_vals = sum(offsets, start=datetime.timedelta(seconds=0))
        return sign * offset_vals

    def parse_duration(self, duration):
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
        # check if we have received week/day 
        if 'w' in duration or 'd' in duration:
            return self.parse_offset(duration), ""

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

    def parse_time(self, time):
        '''
        Transform a given time string into a datetime object.
        
        Absolute time: 
            yyyy/mm/dd_hh:mm:ss (with optionals)
            hh:mm:ss
            etc.
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

        if time == "now":
            return datetime.datetime.now()
        
        if "_" in time:
            date, hour = time.split("_")
            # Day defined
            date = parse_date(date)
            # Time defined
            hour = parse_hms(hour)
            return datetime.datetime.combine(date, hour)
        elif "-" in time:
            # Only a date
            return parse_date(time)
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
            hms = ":".join([k if k else '00' for k in duration])
            hms = datetime.time.fromisoformat(hms)
            return datetime.datetime.combine(datetime.datetime.now(), hms)
        else:
            raise("Unknown date format")

    def interpret_args(self, args, actions):
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

                    elif actions[option]["type"] == ArgType.Offset:
                        print("Parsing offset for ", val)
                        offset = self.parse_offset(val) if val is not None else None
                        proc_args[option] = offset

                    else:
                        proc_args[option] = val

                    args_r = args_r[2:] if len(args_r) > 2 else []


                if args_r == []:
                    break

            else:
                return False, {}, "Error: invalid option {}".format(option)

        return True, proc_args, ""

    def parse_work(self, args):
        '''
        Parse provided work command, and execute it.
        Returns: an information message
        '''
        ret, proc_args, msg = self.interpret_args(args, self.work_actions)
        if not ret:
            return msg

        # Now insert into database
        if "done" in proc_args:
            # Just update last record
            now = datetime.datetime.now()
            # Checks for items whose start time is before now
            # and end time is after now;
            # or items which have no end date yet.
            overlap = self.db.get_overlapping_records(now)
            idx = [k[0] for k in overlap]
            # Only update records 
            self.db.update_records_end(idx, now)
            return

        if not "on" in proc_args:
            return "Error: needs project name"
        else:
            project_name = proc_args["on"]
        if not "at" in proc_args:
            # No start specified => use now
            start_time = datetime.datetime.now()
        else:
            start_time = proc_args["at"]
        if not "for" in proc_args:
            # No duration specified => task open
            end_time = None
        else:
            end_time = start_time + proc_args["for"]

        ## Check if there is an overlap with a *finished* working entry
        # print("Start time is: {}".format(start_time))
        start_overlap = self.db.get_overlapping_records(start_time)
        end_overlap = self.db.get_overlapping_records(end_time)
        has_overlap = len(start_overlap) > 0 or len(end_overlap) > 0
        msg = ''
        if has_overlap:
            if "force" in proc_args:
                # Insert new item
                ret, msg_ = self.db.insert_record_by_name(project_name, start_time, end_time)
                if ret:
                    # Update ovelapping items
                    idx = [k[0] for k in start_overlap] + [k[0] for k in end_overlap]
                    self.db.update_records_end(idx, start_time)
                    return msg + "\n" + msg_ + "\nUpdated {}".format(idx)
                else:
                    return msg_
            else:
                if len(start_overlap) > 0:
                    msg = "Records overlapping start point:\n" \
                        "Use force to update the end values of these records to start tune ({})\n"\
                            .format(start_time)
                    return msg + format_records(start_overlap).get_string()

                if end_time and len(end_overlap) > 0:
                    msg = "Records overlapping end point:\n" + format_records(end_overlap).get_string()
                return msg

        else:
            # Normal insertion
            self.db.insert_record_by_name(project_name, start_time, end_time)
            return "Inserted new record for project {} from {} to {}".format(project_name, start_time, end_time)
    
    @staticmethod
    def date2dt(x):
        '''Make a datetime object based on a given date'''
        return datetime.datetime.combine(x, datetime.time.min)

    def shortcut_to_dates(self, args: str):
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

    def parse_show(self, args):
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
            return msg

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
                start_date = today + proc_args["from"]
                end_date = today    
            if "for" in proc_args:
                end_date = start_date + proc_args["for"]
        
        
        items = self.db.get_records(start_date, end_date)
        items = rep_with_proj_tree(items)
        ret = "Showing from {} to {}".format(start_date, end_date) + "\n"
        ret += format_records(items).get_string()
        return ret
    
    def parse_stats(self, args):
        '''
        Parse provided stats command, and execute it.
        Returns: an information message
        
        Known format: see parse_show
        '''
        ret, proc_args, msg = self.interpret_args(args, self.stats_actions)
        if not ret:
            return msg
        # Get projects list
        tree_s, _, flat_tree, _ = self.db.get_project_tree()
        
        today = self.date2dt(datetime.date.today())

        # default to week view
        if proc_args == {}:
            proc_args = {'thisweek': None}
        start_date, end_date = self.shortcut_to_dates(proc_args)
        if start_date is None or end_date is None:
            if "from" in proc_args:
                start_date = today + proc_args["from"]
                end_date = today    
            if "for" in proc_args:
                end_date = start_date + proc_args["for"]

        items = self.db.get_period_stats(start_date, end_date)

        t = PrettyTable()
        t.field_names = ("Project ID", "Project", "Time spent")
        t.align["Project"] = "l"
        t.align["Time spent"] = "l"

        data = []

        # Total time spent
        tot_duration = sum([k[-1] for k in items])

        # Stats per project
        for proj_idx, _ in tree_s.items():
            proj_children_recursive = self.db.get_children_list(tree_s, proj_idx)
            duration = 0
            for item in items:
                if item[0] == proj_idx:
                    # print("Adding time for {} = {}".format(item[1], datetime.timedelta(seconds=item[2])))
                    duration += item[2]
            for item in items:
                if item[0] in proj_children_recursive:
                    # print("Adding time for child {} = {}".format(item[1], datetime.timedelta(seconds=item[2])))
                    duration += item[2]
            
            proj_name = flat_tree[proj_idx]
            if duration > 0:
                data.append([proj_idx, proj_name, datetime.timedelta(seconds=duration)])

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

        for k in data:
            t.add_row(k)

        t.add_row(("Total", "[All projects]", datetime.timedelta(seconds=tot_duration)))        
        ret = "Stats from {} to {}".format(start_date, end_date) + "\n"

        return ret + t.get_string()


    def parse_edit(self, args):
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
            return msg
        edit_id = None
        project_id = None
        new_start_time = None
        new_end_time = None
        if not "id" in proc_args:
            return "Required parameter `id` is missing."
        else:
            edit_id = int(proc_args["id"])
        
        if "project" in proc_args:
            # Re-assign to a different project
            _, _, _, proj_to_id = self.db.get_project_tree()
            if proc_args["project"] in proj_to_id:
                project_id = proj_to_id[proc_args["project"]]
            else:
                return "Invalid project: {}".format(proc_args["project"])

        if "from" in proc_args:
            # Edit start time
            new_start_time = proc_args["from"]

        if "to" in proc_args:
            # Edit end time
            new_end_time = proc_args["to"]

        # Check overlaps
        start_overlap = self.db.get_overlapping_records(new_start_time) if new_start_time is not None else []
        end_overlap = self.db.get_overlapping_records(new_end_time) if new_end_time is not None else []
        # Ignore this item
        start_overlap = [k for k in start_overlap if k[0] != edit_id]
        end_overlap = [k for k in end_overlap if k[0] != edit_id]

        if len(start_overlap) > 0:
            msg = "Cancelling: Records overlap new start time ({}):\n".format(new_start_time)
            return msg + format_records(start_overlap).get_string()

        if len(end_overlap) > 0:
            msg = "Cancelling: Records overlap new end time ({}):\n"
            return msg + format_records(end_overlap).get_string()
        
        # Update
        self.db.update_record(edit_id, new_start=new_start_time, new_end=new_end_time, new_project_id=project_id)
    
    def parse_delete(self, args):
        '''
        Parse provided delete command, and execute it.
        Returns: an information message

        Example:
        rm id <record_id>
        '''
        
        # Only retrieve IDs
        if len(args) == 0:
            return "Error: no record ID provided"
        ids = [int(k) for k in args] # Ensure only integers are taken
        self.db.delete_records(ids)


    def parse_project(self, args):
        '''
        Parse provided project command, and execute it.
        Returns: an information message
        
        See and edit projects

        project list # Show all
        project add <project path> # Add some project as child of something.
        project id <project id> rename <subproject name>
        project hide <project_id> # Hides a project and its children

        Do we want these ones?
        project rm <project id> # Delete a project. Warning! is used?
        '''

        ret, proc_args, msg = self.interpret_args(args, self.projects_actions)
        if not ret:
            return msg

        tree_s, _, proj_byids, projs_byname = self.db.get_project_tree()

        if len(proc_args) == 0:
            # No args
            proc_args = {'list':None}

        if 'list' in proc_args:
            proj_list = self.db.get_projects()
            proj_names = format_projects(proj_list, proj_byids)
            return proj_names.get_string()
        elif 'add' in proc_args:
            new_project_path = proc_args['add'].split(".")
            new_project_name = new_project_path[-1]
            
            # check if we already have this project
            if proc_args['add'] in projs_byname:
                return "Project already exists, skipping."
            # check if the new project is the child of some other project
            parent_id = None
            if len(new_project_path) > 1:
                project_basepath = ".".join(new_project_path[:-1])
                if project_basepath in proj_byids.values():
                    # get the ID of the parent
                    parent_id = projs_byname[project_basepath]
            self.db.insert_project(new_project_name, parent_id=parent_id)

        elif 'rm' in proc_args:
            # NOTE: dangerous operation. What about children?
            # 1) check if the project has children and if any record using
            # one of these children is present. If not, delete.
            project_name = proc_args['rm']
            project_id = projs_byname[project_name]
            children_list = self.db.get_children_list(tree_s, project_id)
            recs = self.db.get_records_for_projects(children_list + [project_id, ])
            if len(recs) > 0:
                return "Can't delete project {}: used by records: \n".format(project_id) + \
                     ", ".join([str(k[0]) for k in recs])
            
            else:
                self.db.delete_project(project_id)

        elif 'id' in proc_args:
            if 'rename' in proc_args:
                new_name = proc_args["rename"]
                project_id = int(proc_args['id'])
                if "." in new_name:
                    return "Can't change project path. Please rename parent project first."
                if not self.db.rename_project(project_id, new_name):
                    return "Project ID {} doesn't exist.".format(proc_args['id'])
                else:
                    ret = "Updated project ID {}".format(proc_args['id'])
                    proj = self.db.get_project_id(project_id)
                    return ret + "\n" + format_projects(proj, proj_byids).get_string()
            else:
                # Just show it
                proj = self.db.get_project_id(project_id)
                return format_projects(proj, proj_byids).get_string()


    def parse_cmd(self, cmd, args):
        '''
        Execute the appropriate parse function
        '''
        return self.cmds[cmd](args)
        

if __name__ == '__main__':
    pass