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

import sqlite3
import datetime
import copy

from typing import Optional, Tuple, List, Union, Iterable

try:
    from typeguard import typechecked
except ImportError:
    # typechecked is a no-op
    def typechecked(func):
        def inner(*args, **kwargs):
            return func(*args, **kwargs)
        return inner

@typechecked
def to_unixtime(dt: datetime.date):
    """Convert datetime to timestamp, dropping second fractions"""
    return int(datetime.datetime.timestamp(dt))

class RecordDb:
    '''
    Database operations on records and projects
    '''
    @typechecked
    def __init__(self, db_path: str ='work.db') -> None:
        '''Define path to SQLite DB to be used'''
        self.db_path = db_path

    @typechecked
    def create_db(self) -> None:
        '''Create database if not exists'''
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        cur = self.con.cursor()

        # Categories    
        cat_db = """
            CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent INTEGER,
            name TEXT NOT NULL UNIQUE
            );
            """

        # Work entries
        # AUTOINCREMENT prevents the reuse of an id, such that new records will
        # always have the highest id
        records_db = """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                start INTEGER,
                end INTEGER,

                CONSTRAINT fk_project
                    FOREIGN KEY (project_id)
                    REFERENCES projects(id),
                
                CONSTRAINT start_chk CHECK(typeof(start) = 'integer'),
                CONSTRAINT end_chk CHECK(typeof(end) = 'integer' OR end = NULL)

            );
            """

        # Add todos
        todos_db = """
            CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            priority INTEGER DEFAULT 0,
            project_id INTEGER DEFAULT 1,
            open_ts INTEGER,
            done_ts INTEGER,
            due_ts INTEGER,
            descr TEXT NOT NULL,
            
            CONSTRAINT fk_todo_project
                FOREIGN KEY (project_id)
                REFERENCES projects(id),
            
            CONSTRAINT priority_chk CHECK(typeof(priority) = 'integer'),
            CONSTRAINT open_ts_chk CHECK(typeof(open_ts) = 'integer'),
            CONSTRAINT done_ts_chk CHECK(typeof(done_ts) = 'integer' OR done_ts = NULL)
            CONSTRAINT due_ts_chk CHECK(typeof(due_ts) = 'integer' OR done_ts = NULL)
            );
            """
        # Add non-assigned project
        notassigned_proj_req = """INSERT OR IGNORE INTO projects (id, parent, name) VALUES (1, NULL, 'Not assigned')"""

        for i in (cat_db, records_db, todos_db, notassigned_proj_req):
            cur.execute(i)
        


    @typechecked
    def insert_project(self, name: str, parent_id: int=None) -> None:
        '''
        Add a new project as child of an existing one.
        '''
        req = """INSERT INTO projects (parent, name) VALUES (?, ?)"""
        cur = self.con.cursor()
        cur.execute(req, (parent_id, name))
        self.con.commit()

    @typechecked
    def rename_project(self, project_id: int, new_name: str) -> bool:
        '''
        Change a project name
        '''
        cur = self.con.cursor()
        req = """SELECT id FROM projects WHERE id = ?"""
        res = cur.execute(req, (project_id, )).fetchall()
        if len(res) == 0:
            return False

        req = """UPDATE projects set name = ? WHERE id = ?"""
        cur.execute(req, (new_name, project_id, ))
        self.con.commit()
        return True
    
    @typechecked
    def delete_project(self, project_id: int) -> bool:
        '''
        Delete a project
        '''
        cur = self.con.cursor()
        req = """SELECT id FROM projects WHERE id = ?"""
        res = cur.execute(req, (project_id, )).fetchall()
        if len(res) == 0:
            return False

        req = """DELETE FROM projects WHERE id = ?"""
        cur.execute(req, (project_id, ))
        self.con.commit()
        return True

    @typechecked
    def insert_record_by_name(self, project_name: str, start: datetime.datetime, 
                              end: Optional[datetime.datetime]) -> Tuple[bool, str]:
        '''Insert work time for a given project (by name) 
        with specified start and potential end time

        This is safe because the project name must provide the complete
        path to the projects, ie project1.task1.detail1
        '''
        _, _, _, proj_id = self.get_project_tree()
        
        if project_name in proj_id:
            #print("Inserting for project {}, start {}, end {}".format(project_name, start, end))
            return self.insert_record(proj_id[project_name], start, end), ""
        else:
            return False, "Unknown project {}".format(project_name)

    @typechecked
    def insert_record(self, project_id: int, start: datetime.datetime, 
                      end: Optional[datetime.datetime]=None) -> bool:
        req = """INSERT INTO records (project_id, start, end)
                  VALUES (?, ?, ?)"""
        cur = self.con.cursor()
        if end is not None:
            end = to_unixtime(end)
        cur.execute(req, (project_id, to_unixtime(start), end))
        self.con.commit()
        return True

    @typechecked
    def format_record(self, res: List, use_project_name=False) -> List[Tuple]:
        recs = []
        for item in res:
            entry_id = item["rid"]
            project_id = item["name"] if use_project_name else item["pid"]
            start = item["start"]
            end = item["end"]
            if start:
                start = datetime.datetime.fromtimestamp(start)
            if end:
                end = datetime.datetime.fromtimestamp(end) 
            duration = end - start if start and end else None
            recs.append((entry_id, project_id, start, end, duration))
        return recs

    @typechecked
    def update_records_end(self, record_idx: List[int], end_time: datetime.datetime) -> None:
        req = """
                UPDATE records SET end = ? WHERE id = ?
        """
        rec_ends = list(zip((to_unixtime(end_time), ) * len(record_idx), record_idx))
        #print(rec_ends)
        cur = self.con.cursor()
        cur.executemany(req, rec_ends)
        self.con.commit()

    @typechecked
    def update_record(self, record_idx: int, new_start: Optional[datetime.datetime]=None, 
                      new_end: Optional[datetime.datetime] = None, new_project_id: Optional[int] = None) -> None:
        req = """UPDATE records SET """
        # Check what is available
        new_start = to_unixtime(new_start) if new_start is not None else None
        new_end = to_unixtime(new_end) if new_end is not None else None
        items = ("project_id = ?", "start = ?", "end = ?")
        avail_items = (new_project_id, new_start, new_end)
        req += ", ".join([k for k, h in zip(items, avail_items) if h is not None])
        req += " WHERE id = ?"
        cur = self.con.cursor()
        cur.execute(req, [k for k in avail_items if k is not None] + [record_idx,])
        self.con.commit()
        
    @typechecked
    def get_records_by_id(self, record_ids: List[int], format: bool=False) -> Union[List[dict], List[Tuple]]:
        cur = self.con.cursor()
        # Check which records exist
        req = """SELECT r.id AS rid, p.id AS pid, p.name, r.start, r.end FROM records r, projects p
                 WHERE r.project_id = p.id AND r.id IN ("""
        req += ",".join(["?",] * len(record_ids))
        req += ")"
        recs = cur.execute(req, record_ids).fetchall()
        if format:
            return self.format_record([dict(k) for k in recs], use_project_name=True)
        else:
            return [dict(k) for k in recs]


    @typechecked
    def delete_records(self, record_list: List[int]) -> List[int]:
        cur = self.con.cursor()
        # Check which records exist
        recs = self.get_records_by_id(record_list)
        # Keep only record id
        recs = [(k["rid"],) for k in recs]
        req = """DELETE FROM records WHERE id = ?"""
        cur.executemany(req, recs)
        self.con.commit()
        return [k[0] for k in recs]

    @typechecked
    def get_overlapping_records(self, time: Optional[datetime.datetime], format=True) -> List[Union[Tuple, dict]]:
        if time is None: return []
        req = """SELECT r.id AS rid, p.name, r.start, r.end FROM records r, projects p
                 WHERE r.project_id = p.id
                 AND ((r.start < ? AND r.end > ?) OR (r.end IS NULL AND r.start < ?))
                 ORDER BY r.start DESC"""
        cur = self.con.cursor()
        #print("For time: ", time)
        res = cur.execute(req, (to_unixtime(time), ) * 3).fetchall()
        if format:
            return self.format_record([dict(k) for k in res], use_project_name=True)
        else:
            return [dict(k) for k in res]

    @typechecked
    def get_last_records(self, num: int = 1) -> List[dict]:
        req = """SELECT p.id AS pid, r.id AS rid, p.name, r.start, r.end FROM records r, projects p
                 WHERE r.project_id = p.id
                 ORDER BY r.start DESC LIMIT ?"""
        cur = self.con.cursor()
        res = cur.execute(req, ("{}".format(num), )).fetchall()
        return [dict(k) for k in res]

    @typechecked
    def get_records(self, start:datetime.date, 
                          end : Optional[datetime.datetime] = None, desc: bool = False) -> List[Tuple]:
        if not end:
            end = to_unixtime(datetime.datetime.now())

        req = """SELECT r.id AS rid, p.id AS pid, r.start, r.end FROM records r, projects p
                 WHERE r.project_id = p.id
                 AND r.start >= ?
                 AND r.start <= ?
                 ORDER BY r.start 
                """
        if desc:
            req += " DESC"
        cur = self.con.cursor()
        start, end = to_unixtime(start), \
                     to_unixtime(end)
        res = cur.execute(req, (start, end)).fetchall()
        return self.format_record([dict(k) for k in res])

    @typechecked
    def get_ongoing_projects(self) -> List[dict]:
        req = """SELECT r.id AS rid, p.id AS pid, r.start, r.end FROM records r, projects p
                 WHERE r.project_id = p.id AND r.end IS NULL"""
        cur = self.con.cursor()
        res = cur.execute(req).fetchall()

        return [dict(k) for k in res]


    @typechecked
    def get_project_id(self, project_id: int) -> List[Tuple]:
        req = """SELECT id, parent, name FROM projects WHERE id = ?"""
        cur = self.con.cursor()
        project = cur.execute(req, (project_id, )).fetchall()
        return project

    @typechecked
    def get_projects(self) -> List[dict]:
        req = """SELECT id AS pid, parent, name FROM projects"""
        cur = self.con.cursor()
        projects = cur.execute(req).fetchall()
        return [dict(k) for k in projects]

    @typechecked
    def get_records_for_projects(self, project_ids: List[int]) -> List[dict]:
        cur = self.con.cursor()
        req = """SELECT id AS pid FROM records WHERE project_id IN ("""
        req += ", ".join(["?",] * len(project_ids))
        req += ")"
        projects = cur.execute(req, project_ids).fetchall()
        return [dict(k) for k in projects]

    @typechecked
    def get_period_stats(self, start: datetime.datetime, end: Optional[datetime.datetime]) -> List[dict]:
        '''
        Count the number of hour per project in the specified period.
        Also report stats per project
        '''
        if not end:
            end = to_unixtime(datetime.datetime.now())

        req = """SELECT r.project_id AS pid, p.name, SUM(r.end - r.start) AS duration FROM records r, projects p
                 WHERE r.project_id = p.id
                 AND r.start >= ?
                 AND r.end <= ?
                 GROUP BY r.project_id
                 ORDER BY r.start 
                """
        cur = self.con.cursor()
        start, end = to_unixtime(start), \
                     to_unixtime(end)
        res = cur.execute(req, (start, end)).fetchall()
        return [dict(k) for k in res]

    @typechecked
    def get_project_tree(self) -> Tuple[dict, dict, dict, dict]:
        '''Retrieve the whole project list
        
        Returns:
        - A hashmap of projects, with index as keys
        - A hashmap of projects, with names as keys
        - A flattened hashmap of projects  indexed by name, in format project.subproject.subsubproject
          with the index as value
        '''
        req = """SELECT id, parent, name FROM projects;"""
        cur = self.con.cursor()
        projects = cur.execute(req).fetchall()

        # Test: ensure not position-dependent
        # import random
        # random.shuffle(projects)

        # Whole tree indexed by ID
        tree_s = {idx: {"name": name, "parent": parent, "children": {}, "children_idx":[], "rec_children":[] } \
                    for idx, parent, name in projects}

   
        # Add children index information
        for idx, item in tree_s.items():
            parent = item["parent"]
            if parent is not None:
                tree_s[parent]["children_idx"].append(idx)

        tree_t = copy.deepcopy(tree_s)

        def add_children(tree, tree_s):
            for idx, item in tree.items():
                # print(item)
                children = item["children_idx"]
                for child_idx in children:
                    new_child_name = child_idx
                    new_child_data = copy.deepcopy(tree_s[child_idx])
                    tree[idx]["children"][new_child_name] = new_child_data
                    add_children(tree[idx]["children"], tree_s)  

        add_children(tree_t, tree_s)  


        # Delete non-root items
        tree_t = {k:v for k, v in tree_t.items() if v["parent"] is None}   

        tree_c = copy.deepcopy(tree_t)


        # Find all leaf projects: nodes that noone has as parent.

        def flatten_tree(tree, parent, flat_dict):
            # First rename keys
            for idx, item in tree.items():
                if parent != '':
                    tree[idx]["name"] = parent + "." + tree[idx]["name"]

            for idx, item in tree.items():
                flat_dict[idx] = item["name"]

            for idx, item in tree.items():                
                flatten_tree(tree[idx]["children"], item["name"], flat_dict)

        flat_list = {}
        flatten_tree(tree_c, '', flat_list)
        # reverse:
        flat_list_rev = dict(zip(flat_list.values(), flat_list.keys()))

        return tree_s, tree_t, flat_list, flat_list_rev

    @typechecked
    def get_children_list(self, tree: dict, index: int) -> List[int]:
        '''
        Uses `tree`, hashmap of projects indexed by id to determine
        the ids of all subprojects (recursively)
        '''
        children_list = tree[index]["children_idx"]
        children = children_list.copy()
        while True:
            if len(children_list) == 0:
                break
            idx = children_list.pop()
            children_list += tree[idx]["children_idx"]
            children += tree[idx]["children_idx"]
            
        return children

    @typechecked
    def get_todos(self, opened_only=False, closed_only=False, due_only=False, orderby: Iterable[str] = None) -> List[dict]:
        if opened_only and closed_only:
            raise "open_only and closed_only are mutually exclusive"
        cond = ""
        if opened_only:
            cond = "WHERE t.done_ts IS NULL"
        if closed_only:
            cond = "WHERE t.done_ts IS NOT NULL"
        if due_only:
            if cond == "":
                cond += " WHERE "
            else:
                cond += " AND "
            cond += "t.due_ts IS NOT NULL"

        ordering = {"opened" : "open_ts", "closed": "close_ts", "due": "due_ts",
                   "project": "pid", "id": "tid"}

        sort = ""
        if orderby:
            sort = "ORDER BY " + ", ".join([ordering[k] for k in orderby if k in ordering]) + " DESC"

        req = """SELECT t.id AS tid, t.project_id, t.priority, t.open_ts, t.done_ts, t.due_ts, t.descr""" \
              """, p.id AS pid, p.name AS project_name FROM todos t """ \
              """ LEFT JOIN projects p ON t.project_id = p.id {} {}""".format(cond, sort)
        cur = self.con.cursor()
        todos = cur.execute(req).fetchall()
        return [dict(k) for k in todos]

    @typechecked
    def get_todo_by_ids(self, ids: Iterable[int]) -> List[dict]:
        req = """SELECT t.id AS tid, t.project_id, t.priority, t.open_ts, t.done_ts, t.due_ts, t.descr""" \
              """, p.id AS pid, p.name AS project_name FROM todos t """ \
              """ LEFT JOIN projects p ON t.project_id = p.id WHERE tid IN ({})""" \
              .format(", ".join([str(k) for k in ids]))
        cur = self.con.cursor()
        todos = cur.execute(req).fetchall()
        return [dict(k) for k in todos]

    @typechecked
    def insert_todo(self, descr,  project_idx: Optional[int] = None, 
                    due : Optional[datetime.datetime] = None, 
                    priority: Optional[int] = None) -> None:
        '''
        Insert a new todo
        '''
        if due:
            due = to_unixtime(due)
        if not priority:
            priority = 0

        req = """INSERT INTO todos (project_id, priority, open_ts, done_ts, due_ts, descr)
                  VALUES (?, ?, strftime('%s','now'), NULL, ?, ?)"""
        cur = self.con.cursor()
        cur.execute(req, (project_idx, priority, due, descr))
        self.con.commit()

    @typechecked
    def delete_todos(self, todo_idx: Iterable[int]) -> Optional[List[dict]]:
        recs = self.get_todo_by_ids(todo_idx)
        req = """DELETE FROM todos WHERE id IN ({})""" \
                .format(", ".join([str(k["tid"]) for k in recs]))
        cur = self.con.cursor()
        cur.execute(req)
        self.con.commit()
        return recs

    @typechecked
    def close_todo(self, todo_idx: int, done_ts: datetime.datetime = None) -> Optional[List[dict]]:
        recs = self.get_todo_by_ids((todo_idx,))
        if len(recs) == 1:
            req = """UPDATE todos SET done_ts = ? WHERE id = ?"""
            cur = self.con.cursor()
            cur.execute(req, (done_ts.timestamp(), recs[0]["tid"]))
            self.con.commit()
        return recs

    @typechecked
    def update_todo_project(self, todo_idx: int, project_id: int = None) -> Optional[List[dict]]:
        recs = self.get_todo_by_ids((todo_idx,))
        if len(recs) == 1:
            req = """UPDATE todos SET project_id = ? WHERE id = ?"""
            cur = self.con.cursor()
            cur.execute(req, (project_id, recs[0]["tid"]))
            self.con.commit()
        return recs


def pretty(d, indent=0):
   for key, value in d.items():
      print('\t' * indent + str(key))
      if isinstance(value, dict):
         pretty(value, indent+1)
      else:
         print('\t' * (indent+1) + str(value))
        


if __name__ == "__main__":
    db = RecordDb(db_path="/home/tnorth/personal/worktime/work.db")
    db.get_ongoing_projects()
    import sys
    sys.exit(0)
    tree_s, tree_n, tree_flat, tree_flat_rev = db.get_project_tree()
    print("TREE_S")
    pretty(tree_s)
    print("TREE_N")
    pretty(tree_n)
    print("TREE_FLAT")
    print(tree_flat)
    print("TREE_FLAT REV")
    print(tree_flat_rev)
    print(db.get_children_list(tree_s, 5))
    print(db.get_records_for_projects((11, 13)))
