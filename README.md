# Worktime - A simple command-line time tracker

Helps you track the time spent on projects via a minimal set of command.

## Releases

There is no stable release at the time

## Installation

Worktime is a Python module. It can be installed using:

```
python setup.py install
```

## Features

Worktime is a command-line tool backed by a SQLite database, designed for the following use-case:

**Record on which project one is working, at what time and for how long.**

This task must be performed with the minimum possible overhead, therefore worktime provides:
- a minimal set of commands for interacting with work/on project records,
- a comprehensible and complete help, including example for each possible command.

Concretely, time spent on projects is recorded so that the following questions can be answered:
- How much time was spent on project X in period T ?
- How was the total time in period T distributed on projects X0, X1, ... ?

That's all you will get with Worktime.

## Concepts

Worktime knows only of **projects** and **records**.

### Projects

Something that one spends time on:
- have a name,
- may have a parent project.

A slice of time spent on a project is a **record**.

### Records

The record of time spent on a **project**..
- points to an existing **project**,
- has a start date/time, and an end date/time (optional)


## Example use (Quickstart)

### Define a project

```
(wt) project add ProjectName
Added project ProjectName
```

If your project is a child of another existing project, use "." as a hierarchical separator:
```
(wt) project add ProjectName.Subproject1
Added project Subproject1
```

See what you have created:
```
(wt) project
# Or:
(wt) project list
+----+-------------------------+
| ID | Project path            |
+----+-------------------------+
| 1  | ProjectName             |
| 2  | ProjectName.Subproject1 |
+----+-------------------------+
```

## Log work on a project

```
# Start now, in progress
(wt) work on ProjectName
# ... after some time, when you stop working on that project:
(wt) work done
# ... or start working on something else, it will close the current record
(wt) work on OtherProject
# Log work but already specify a duration
#  support syntax example: 2h, 2h10m30s, 1:00 (1 minute), 
(wt) work on ProjectName for 2h
# Specify a start date/time (when one forgets to log the work's start)
# supported syntax example: 9:00, 2020-04-15_9:10
(wt) work on ProjectName at 10:05
# Log work for a past time period
(wt) work on ProjectName.Subproject1 at 10:00 until 12:30
```

## Display

### Show records

```
# no argument => today
(wt) show
Showing from 2021-04-15 00:00:00 to 2021-04-16 00:00:00
+----+-------------+---------------------+---------------------+----------+
| ID | Project     | Start time          | End time            | Duration |
+----+-------------+---------------------+---------------------+----------+
| 1  | ProjectName | 2021-04-15 10:41:26 | 2021-04-15 12:41:26 | 1:00:00  |
+----+-------------+---------------------+---------------------+----------+
# Known aguments: today, yesterday, thisweek, lastweek, thismonth, lastmonth
(wt) show thisweek
# (Similar output)
# Use `from` and `for` with a duration
(wt) show from 2021-04-01_10:00 for 1w
# Or with a relative time
(wt) show from -1w for 1w
```

### Show projects

```
# no argument => project list
(wt) project list
+----+-------------------------+
| ID | Project path            |
+----+-------------------------+
| 1  | ProjectName             |
| 2  | ProjectName.Subproject1 |
+----+-------------------------+
```

### Show period summary (stats)

```
# no argument => thisweek
(wt) stats
+------------+--------------------------+------------+
| Project ID | Project                  | Time spent |
+------------+--------------------------+------------+
|     1      | ProjectName              | 1:00:00    |
|     2      |           └─Subproject1  | 0:00:00    |
|   Total    | [All projects]           | 1:00:00    |
+------------+--------------------------+------------+
# Specify period
# See show command for usage
(wt) stats from -1w for 1d
# Stats thismonth
Stats from 2023-07-01 00:00:00 to 2023-08-01 00:00:00
+------------+----------------+------------+-------------------------+
| Project ID | Project        | Time spent | Graph                   |
+------------+----------------+------------+-------------------------+
|     4      | ProjectName    | 64.38 h    | ██████████████████████▍ |
|     12     | Project2       | 15.62 h    | █████▍                  |
|     13     | Project3       | 6.19 h     | ██▏                     |
|   Total    | [All projects] | 86.18 h    | 3 days, 14:11:01        |
+------------+----------------+------------+-------------------------+
# Stats by week
(wt) stats thismonth byweek
Stats from 2023-07-01 00:00:00 to 2023-08-01 00:00:00
+------------+----------------+----------------+----------------+----------------+----------------+----------------+----------------+-------------------------+
| Project ID | Project        | 01-07 to 03-07 | 03-07 to 10-07 | 10-07 to 17-07 | 17-07 to 24-07 | 24-07 to 31-07 | 31-07 to 01-08 | Total                   |
+------------+----------------+----------------+----------------+----------------+----------------+----------------+----------------+-------------------------+
|     4      | ProjectName    | 0.00 h         | 36.45 h        | 27.93 h        | 0.00 h         | 0.00 h         | 0.00 h         | ██████████████████████▍ |
|     12     | Project1       | 0.00 h         | 3.32 h         | 3.70 h         | 0.00 h         | 8.59 h         | 0.00 h         | █████▍                  |
|     13     | Project2       | 0.00 h         | 0.00 h         | 6.19 h         | 0.00 h         | 0.00 h         | 0.00 h         | ██▏                     |
|   Total    | [All projects] | 0.00 h         | 39.77 h        | 37.82 h        | 0.00 h         | 8.59 h         | 0.00 h         | 86.18 hours             |
+------------+----------------+----------------+----------------+----------------+----------------+----------------+----------------+-------------------------+
# etc.
```

### Edit a record

```
# Edit record 5: assign to Subproject1 and set start to today, 10:00, and end to today, 11:00
(wt) edit id 5 project ProjectName.Subproject1 from 10:00 to 11:00
```

### Delete a record

```
# Accepts a list of records
(wt) rm 5 6 7 42
```

### Rename a project

```
(wt) project id 2 rename ProjectName.Subproject2
```

### Delete a project
This is allowed only for projects which weren't used
```
(wt) project rm 2
```

## Comparison to OpenSource (libre) alternatives

Worktime is minimal, and therefore not really comparable to alternatives.

Here a list of other client programs for a use-case similar to worktime:

- [Project Hamster](https://projecthamster.wordpress.com/about/) : Linux, Python/PyGTK, GUI, GPLv3
- [Task Coach](https://www.taskcoach.org/): multi-platform, Python/wxPython, GUI, GPLv3
- [Rachota](http://rachota.sourceforge.net/en/index.html) : multi-patform, Java, GUI, CCDL
- [TimeSlotTracker](https://github.com/TimeSlotTracker/timeslottracker-desktop) : multi-patform, Java, GUI, License unknown
- [KTimeTracker](https://userbase.kde.org/KTimeTracker) : Linux, C++/Qt, GUI, GPLv2
- [GTimeLog](https://gtimelog.org/) : Linux, Python/GTK, Mixed (GUI with command prompt)

The closest alternative is probably GTimeLog, which is also controlled by textual inputs.


## Contributing

Any contribution is highly appreciated. Please create a pull request on GitHub.

## License

This program is licensed under the GNU General Public License v3. Please see the COPYING file for details.
