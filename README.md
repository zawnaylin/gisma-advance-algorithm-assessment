# Campus Puzzle — University Timetabling

This project assigns a university's classes to **rooms** and **time slots** for a
five-day week (Monday–Friday, 09:00–17:00) without breaking any hard
constraint. It is built in four stages, each one handling a part of the problem
the previous stage left open:

| Stage | Engine | File | Answers |
|---|---|---|---|
| 1 | Greedy baseline | `greedy_solver.py` | a decent schedule, instantly |
| 2 | Graph colouring | `graph_engine.py` | which time slots are safe from collisions |
| 3 | Dynamic programming | `room_allocator.py` | which room, with the least wasted capacity |
| 4 | Backtracking + best effort | `backtracker.py` | what to do when nothing above is complete |

## Running

```bash
uv sync
uv run python main.py      # all four stages on every scenario, with the report figures
uv run pytest              # test suite
```

## Project structure

```
main.py                       runs Stages 1-4 on every scenario and prints each report's figures
scenarios/                    problem instances (JSON) - see scenarios/README.md
src/
├── domains/                  the problem vocabulary
│   ├── constraints.py        school day (9-17), teaching days (Mon-Fri), max class length
│   ├── class_information.py  a class: size, duration, professor
│   ├── room.py               a room and its capacity
│   ├── professor.py
│   ├── student_group.py      a cohort: classes its students all attend
│   ├── time_slot.py          day + start/end hour, with an overlap test
│   └── schedule.py           the timetable: validate / add_assignment / unassign
├── data/
│   ├── assignment.py         one placed class (class, room, professor, time slot)
│   └── loader.py             reads a scenario JSON into domain objects
└── algorithms/
    ├── solver.py             Solver protocol, SolveResult, Conflict, manual-intervention report
    ├── instance.py           shared lookups, difficulty ordering, failure diagnosis
    ├── greedy_solver.py      Stage 1
    ├── graph_engine.py       Stage 2 (Welsh-Powell colouring, SlotMap)
    ├── room_allocator.py     Stage 3
    └── backtracker.py        Stage 4
tests/                        unit tests mirroring src/
```

## The problem

A class is placed in one **(time slot, room)** pair. `Schedule.validate` checks
every hard constraint:

| Constraint | Rule |
|---|---|
| Capacity | the room has at least as many seats as the class has students |
| Room clash | a room hosts at most one class at a time |
| Professor clash | a professor teaches at most one class at a time |
| Cohort clash | two classes that share a student group cannot overlap |
| Working hours | a class runs Mon–Fri, starting at 09:00 or later and ending by 17:00 |

Every stage returns the same `SolveResult`. A class that can't be placed is
never dropped silently. `Instance.diagnose` gives it a cause, which is one of two
kinds:

- **Structural**: no search can fix it. The causes are `no_room_large_enough`,
  and `professor_overloaded` (the professor is booked for more than the 40
  teachable hours in a week).
- **Contention**: a better search might fix it. The causes are
  `room_contention`, `professor_contention`, `group_contention` and
  `search_exhausted`.

`Instance.capacity_deficits` also reports the case where more teaching hours
need rooms of a given size than those rooms can supply in a week. That shortfall
is impossible to schedule even though each class on its own has a room that
fits.

The scenarios (`baseline`, `tight`, `cohorts`, `infeasible`) each change one
pressure at a time. They are described in [`scenarios/README.md`](scenarios/README.md).

---

## Stage 1: Greedy baseline (the "quick start")

**Mission.** Create a decent schedule instantly.

**Logic** (`greedy_solver.py`)

1. Sort the classes by difficulty (`Instance.most_constrained_first`), hardest
   first.
2. For each class, go through its legal time slots in chronological order and,
   inside each slot, the rooms big enough for it from smallest to largest.
   Commit the **first** (slot, room) pair that breaks no hard constraint.
3. If there is no such pair, record the class as unplaced, with its cause. A
   decision is never revisited.

The rooms are tried from smallest to largest, so the first available room is
also the snuggest one ("best fit"). Small classes don't take the large halls
that only big classes can use.

**Report: why this sorting key?** The key is
`(duration, number of students, number of cohorts)`, all descending:

- **Duration** comes first because a long class has the fewest legal windows. A
  1-hour class can start at 40 different times in a week, a 3-hour class at only
  30. Longer classes are also harder to fit around the ones already placed.
- **Number of students** comes next because a large class fits in fewer rooms.
  In `infeasible`, a 400-student class fits in none. Larger classes are harder
  to fit, so they are placed first.
- **Number of cohorts** breaks the remaining ties. A class shared by several
  student groups clashes with several timetables at once.

The flexible classes (short, small, in one cohort) are placed last, when they
can still use whatever space is left.

**Result.** 100% coverage on `baseline`. On `tight`, `cohorts` and `infeasible`
the schedule is incomplete: 7, 31 and 39 classes are left unplaced.

---

## Stage 2: Graph colouring (the "collision" engine)

**Mission.** Prevent scheduling conflicts before they happen.

**Logic** (`graph_engine.py`)

1. **Build the conflict graph.** There is one node per class, and an edge
   between two classes if they share a professor or at least one student group
   (`build_graph`).
2. **Colour it with Welsh–Powell.** The colours are time slots.
   - Sort the nodes once by degree, highest first. The class that collides with
     the most others is the hardest to fit, so it goes first. Ties go to the
     longer class, then the larger one.
   - Give each node the first time slot that doesn't overlap any slot already
     given to one of its neighbours.

   The textbook version goes colour by colour, sweeping the sorted list. It
   produces the same colouring as this node-by-node first fit.
3. A colour is only useful if some room is free in it, so each class also gets a
   provisional room. Stage 3 keeps the time slots and redoes the rooms.
4. **Slot map.** After colouring, `SlotMap` labels every candidate window of
   every class as **safe** (no neighbour in an overlapping slot) or **unsafe**,
   and records which neighbours make it unsafe. `main.py` prints a summary for
   each scenario and a weekly grid for the most boxed-in classes.

Because classes have different durations, two neighbours can clash without
sharing exactly the same slot. So "different colour" is read as "slots that
don't overlap".

**Report: greedy vs graph colouring.** Unplaced classes for each scenario:

| scenario | Stage 1 greedy | Stage 2 Welsh–Powell | safe class-windows (slot map) |
|---|---|---|---|
| `baseline` | 0 | 0 | 73.7% |
| `tight` | 7 | **0** | 64.6% |
| `infeasible` | 39 | **32** | 58.8% |
| `cohorts` | **31** | 34 | 7.1% (34 classes with no safe window) |

*Did graph colouring prevent more conflicts?* On three of the four scenarios,
yes:

- **`tight`**: every class is placed (0 unplaced against 7).
- **`infeasible`**: all 7 room-contention failures are recovered. The 32 that
  remain are all structural, so nothing more is possible.
- **Why (likely):** greedy orders the classes by duration and then size, so
  the large lectures come early and fill the same early hours, competing for
  the few big rooms. Welsh–Powell orders them by how many classes they collide
  with. That mixes large and small classes, and seems to spread the load on
  the big rooms across the week.
- **`cohorts`** is the exception (34 against 31). Each cohort carries about 30
  hours, and only 7.1% of all windows are safe. Welsh–Powell fixes its order
  once, from the degrees at the start. It can't react when a low-degree class
  runs out of windows as the graph fills up. This is where a colouring that
  re-chooses the next class as it goes would do better than a fixed order.
- The slot map explains the failures. On `cohorts`, the 34 classes Welsh–Powell
  can't place are exactly the 34 whose every window is marked unsafe. By the
  time their turn came, their neighbours had taken every window.

**Result.** A time slot for each class with no professor or cohort collision,
plus a map of safe and unsafe time slots for each class (`SlotMap`).

---

## Stage 3: Dynamic programming (the "efficiency" engine)

**Mission.** Assign rooms so that wasted capacity is as small as possible,
keeping the time slots from Stage 2 fixed.

**Logic** (`room_allocator.py`). The allocator goes through each day hour by
hour, handling one time slot at a time. At each hour it gives rooms to the
classes that start then, choosing from the rooms not still occupied by a class
that started earlier. Each of these per-slot problems is a minimum-waste
assignment of *n* classes to *m* free rooms, solved by DP:

**DP state.** Sort the classes by size `s₁ ≤ … ≤ sₙ` and the free rooms by
capacity `c₁ ≤ … ≤ cₘ`.
`W[i][j]` is the least wasted capacity for seating the *i* smallest classes
using only the *j* smallest rooms (∞ if that's impossible).

**Recurrence**

```
W[0][j] = 0                         (nobody to seat)
W[i][0] = ∞            for i > 0    (no rooms left)
W[i][j] = min( W[i][j-1],                              room j left empty
               W[i-1][j-1] + cⱼ − sᵢ   if cⱼ ≥ sᵢ )      room j given to class i
answer  = W[n][m]; the actual rooms are recovered by walking the table backwards
```

**Why this avoids checking every combination.** Suppose a smaller class sits in
a bigger room than a larger class. Swapping them keeps both feasible, because
each room still holds its class. It also leaves the waste unchanged, because the
same rooms are in use. So some optimal allocation never "crosses", and the DP
only needs to look at those. That takes *n × m* table cells instead of the
*m!/(m−n)!* ways of handing out rooms. For 10 classes and 50 rooms, that's 500
cells instead of about 3.7 × 10¹⁶ allocations. A test checks the DP against
brute force on 200 random slots (`tests/algorithms/test_room_allocator.py`).

The best choice at each slot isn't automatically the best choice for the whole
day, because a room chosen at 09:00 may still be busy at 10:00. So each day is
compared with the rooms it came in with and kept only if it wastes no more.
Stage 3 therefore never makes a schedule worse. The final schedule is rebuilt
through `Schedule.add_assignment`, which checks every hard constraint again.

**Result: wasted seats** (empty seats summed over all placements):

| scenario | Stage 1 greedy | Stage 2 provisional rooms | Stage 3 DP | DP vs greedy |
|---|---|---|---|---|
| `baseline` | 4,787 | 3,242 | 3,237 | **−32.4%** |
| `cohorts` | 2,965 | 2,509 | 2,509 | **−15.4%** |
| `infeasible` | 2,136 | 1,893 | 1,893 | **−11.4%** |
| `tight` | 9,575 | 9,342 | 9,342 | **−2.4%** |

How to read these figures:

- The final schedule wastes fewer seats than the greedy baseline on every
  scenario.
- Most of that saving comes from the time slots Stage 2 chose. Spreading the
  large classes over the week means fewer small classes end up in large rooms
  because every snug room is busy.
- The DP itself changes little: 5 seats on `baseline`, nothing elsewhere. The DP
  is exact for each slot, so this shows that the best-fit provisional rooms
  were already optimal slot by slot.
- The remaining waste comes from the timetable itself. In a busy hour, small
  classes have to use large rooms, and no room allocation can fix that once the
  time slots are fixed.

---

## Stage 4: Backtracking and the "best effort" strategy

**Mission.** Handle the cases where the earlier stages can't produce a complete
schedule.

**Logic** (`backtracker.py`)

1. **First pass.** Place the classes greedily, most constrained first. A class
   that no room can hold is ruled out immediately.
2. **Recursive repair.** For each class still unplaced, `_attempt(class, depth)`:
   - takes a free (slot, room) if there is one;
   - otherwise, for each (slot, room), finds the **blockers**: scheduled classes
     that overlap this slot and use the same room, the same professor or a
     shared cohort;
   - removes the blockers, places the class, and **recursively** re-places each
     removed class with `depth − 1`;
   - if any removed class can't be re-placed, **backtracks**: a transaction log
     undoes every change since the savepoint, and the next (slot, room) is
     tried.

   This is backtracking aimed at the classes that are actually in the way. Plain
   chronological backtracking undoes the most recent decision first. But the
   decision that stranded a class was usually made hundreds of placements
   earlier. In testing, 300,000 steps of chronological backtracking recovered
   nothing on any scenario.

**Best effort.** A repair is only committed when every class it disturbed found
a new place, so the number of unplaced classes never goes up. Whenever the
search stops (solved, out of options, or out of budget), the schedule it holds
is the fewest-conflict state it reached. Every class still unplaced is
**flagged for manual intervention**, with its cause and a suggested action
(`SolveResult.manual_intervention_report`):

```
FLAGGED FOR MANUAL INTERVENTION: 34 class(es)
  no_room_large_enough -> split the class into sections or book a larger venue
    C0001, C0002, ...
  professor_overloaded -> reassign some of these classes to another professor
    C0090, C0069, ...
  search_exhausted -> rerun with a larger search budget or place by hand
    C0045, C0030
```

**Report: pruning strategy.** The search space (every class × every window ×
every room, with every order of trying them) is cut down in these ways:

| Pruning | What it removes |
|---|---|
| Candidates are generated legal | rooms too small for the class, and windows outside 09:00–17:00, are never generated (`candidate_rooms`, `candidate_slots`) |
| Structural check up front | a class no room can hold is ruled out before any search, instead of failing in every branch |
| Most-constrained-first order | hard classes are placed while there is still plenty of space, so dead ends show up early |
| Best-fit room order | small classes don't take big rooms, which avoids conflicts that would otherwise need repair |
| Free placement first | nothing is moved while a free spot exists |
| Ejection limit (`max_ejections = 2`) | placements that would move 3 or more classes are skipped |
| Depth limit (`depth = 3`) | chains of moves are cut off after 3 levels |
| Directed backtracking | only the classes actually blocking the target are moved, not the most recent decision |
| Exact undo | `Schedule.unassign` lets each failed branch be undone in place, without rebuilding the timetable |
| Step budget (200,000 checks) | guarantees the search ends, and the result is then reported as best effort |

**Result.**

| scenario | Stage 1 greedy | Stage 4 backtracking | notes |
|---|---|---|---|
| `baseline` | 100% | 100% | nothing to repair |
| `tight` | 97.1% | **100%** | all 7 stranded classes placed by moving other classes |
| `infeasible` | 83.8% | **85.8%** | 5 placed after moving others; 32 structural + 2 flagged |
| `cohorts` | 87.1% | 87.1% | the budget ran out; all 31 flagged for manual intervention |

On `infeasible` no algorithm can reach 100%. 17 classes are larger than the
largest room, which holds 120 seats (12 of them have 400 students, the other 5
have between 140 and 186). Professor P999 is booked for 60 hours in a 40-hour
week, and there is a separate 6-hour capacity deficit. The report keeps
*impossible* failures apart from ones *a better search might recover*.
