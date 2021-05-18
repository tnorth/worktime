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

import worktime.record as rec
import worktime.cmd as cmd
import worktime.db as db

def main():
    import sys
    import os
    import pathlib
    if len(sys.argv) == 1:
        database_path = (pathlib.Path(os.getenv("XDG_DATA_HOME", "~/.local/share/")) / "worktime").expanduser()
        database_filepath = database_path / "work.sqlite"
    else:
        database_filepath = pathlib.Path(sys.argv[1])
        database_path = database_filepath.parents[0]
        sys.argv = [sys.argv[0],] # Don't let the terminal interpret the given arg

    database_path.mkdir(parents=True, exist_ok=True)

    db_ = db.RecordDb(db_path=str(database_filepath))
    db_.create_db()

    parser = rec.CmdParser(db=db_)

    w_cmd = cmd.WorkCmd(parser)
    w_cmd.cmdloop()
