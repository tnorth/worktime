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

from typing import Optional, Tuple, List

try:
    from typeguard import typechecked
except ImportError:
    # typechecked is a no-op
    def typechecked(func):
        def inner():
            func()
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
        records_db = """
                    CREATE TABLE IF NOT EXISTS records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER,
                        start INTEGER,
                        end INTEGER,

                        CONSTRAINT fk_project
                            FOREIGN KEY (project_id)
                            REFERENCES projects(id)
                    );
                  """
        for i in (cat_db, records_db):
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
    def format_record(self, res: List) -> List[Tuple]:
        recs = []
        for item in res:
            entry_id, project_id, start, end = item
            if start:
                start = datetime.datetime.fromtimestamp(start)
            if end:
                end = datetime.datetime.fromtimestamp(end) 
            duration = end - start if start and end else None
            recs.append((entry_id, project_id, start, end, duration))
        return recs

    @typechecked
    def update_records_end(self, record_idx: int, end_time: datetime.datetime) -> None:
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
    def delete_records(self, record_list: List[int]) -> None:
        req = """DELETE FROM records WHERE id = ?"""
        cur = self.con.cursor()
        cur.execute(req, record_list )
        self.con.commit()

    @typechecked
    def get_overlapping_records(self, time: Optional[datetime.datetime]) -> List[Tuple]:
        if time is None: return []
        req = """SELECT r.id, p.name, r.start, r.end FROM records r, projects p
                 WHERE r.project_id = p.id
                 AND ((r.start < ? AND r.end > ?) OR (r.end IS NULL AND r.start < ?))
                 ORDER BY r.start DESC"""
        cur = self.con.cursor()
        #print("For time: ", time)
        res = cur.execute(req, (to_unixtime(time), ) * 3).fetchall()
        return self.format_record(res)

    @typechecked
    def get_last_records(self, num: int = 1) -> List[Tuple]:
        req = """SELECT r.id, p.name, r.start, r.end FROM records r, projects p
                 WHERE r.project_id = p.id
                 ORDER BY r.start DESC LIMIT ?"""
        cur = self.con.cursor()
        res = cur.execute(req, ("{}".format(num), )).fetchall()
        return self.format_record(res)

    @typechecked
    def get_records(self, start:datetime.date, 
                          end : Optional[datetime.datetime] = None, desc: bool = False) -> List[Tuple]:
        if not end:
            end = to_unixtime(datetime.datetime.now())

        req = """SELECT r.id, p.id, r.start, r.end FROM records r, projects p
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
        return self.format_record(res)

    @typechecked
    def get_project_id(self, project_id: int) -> List[Tuple]:
        req = """SELECT id, parent, name FROM projects WHERE id = ?"""
        cur = self.con.cursor()
        project = cur.execute(req, (project_id, )).fetchall()
        return project

    @typechecked
    def get_projects(self) -> List[Tuple]:
        req = """SELECT id, parent, name FROM projects"""
        cur = self.con.cursor()
        projects = cur.execute(req).fetchall()
        return projects

    @typechecked
    def get_records_for_projects(self, project_ids: List[int]) -> List[Tuple]:
        req = """SELECT id FROM records WHERE project_id IN (?)"""
        cur = self.con.cursor()
        proj_ids = ", ".join([str(k) for k in project_ids])
        projects = cur.execute(req, proj_ids).fetchall()
        return projects

    @typechecked
    def get_period_stats(self, start: datetime.datetime, end: Optional[datetime.datetime]) -> List[Tuple]:
        '''
        Count the number of hour per project in the specified period.
        Also report stats per project
        '''
        if not end:
            end = to_unixtime(datetime.datetime.now())

        req = """SELECT r.project_id, p.name, SUM(r.end - r.start) AS duration FROM records r, projects p
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
        return res

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

def pretty(d, indent=0):
   for key, value in d.items():
      print('\t' * indent + str(key))
      if isinstance(value, dict):
         pretty(value, indent+1)
      else:
         print('\t' * (indent+1) + str(value))


if __name__ == "__main__":
    db = RecordDb()
    db.create_db()
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