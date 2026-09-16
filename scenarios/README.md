# Scenarios

Each file is one complete instance: rooms, classes and student groups. They are
derived from the baseline (`baseline.json`) by changing one pressure at a
time, so a difference in the result points at a single cause. The teaching load
is always 480 hours across 240 classes; only the resources and the cohort
structure change.

Load one with `data.loader.load_scenario(name)`, or run `python main.py` to see
all four reported.

| scenario | what it stresses | greedy | dominant conflict |
|---|---|---|---|
| `baseline` | nothing - comfortable estate | 100.0% | none |
| `tight` | rooms: 13 rooms, 92% of their hours needed | 97.1% | `room_contention` (7) |
| `cohorts` | cohorts: 60 groups carrying ~30h each | 87.1% | `group_contention` (31) |
| `infeasible` | three impossibilities at once | 83.8% | structural (32) + contention (7) |

## baseline

50 rooms, 159 professors, 60 cohorts of 5 classes. Everything fits, so this is
the control: a conflict here means a bug, not a hard instance.

## tight

The estate cut to 13 rooms, with every capacity tier still represented in
proportion, so 480 teaching hours compete for 520 room-hours. No tier is
oversubscribed - `capacity_deficits` is empty - so nothing is provably
impossible, and greedy's 7 misses are purely the cost of never reconsidering an
early choice. This is the scenario a backtracking search should beat.

Note that deficit-free is necessary but not sufficient: it rules out a proven
impossibility, it does not prove a perfect schedule exists.

## cohorts

The estate is untouched; the cohorts are rebuilt so each of the 60 groups
carries about 30 hours of classes, and a class sits in several cohorts. Rooms
and professors are free all week, so the binding constraint is a cohort's own
timetable - the one failure mode the other scenarios never trigger.

## infeasible

Deliberately unsolvable, in three independent ways at once, so the report has to
separate causes rather than emit a single number:

1. 12 classes of 400 students, larger than any remaining room - `no_room_large_enough`
2. professor `P999` carrying 60 hours of teaching in a 40-hour week - `professor_overloaded`
3. only 11 rooms, which both strands classes (`room_contention`) and leaves a
   6-hour shortfall that shows up as a `capacity_deficit`

The first two are per-class and structural. The third is the interesting one: a
capacity deficit is invisible to any per-class check, because every one of those
classes has a room that fits - they just cannot all have one at once. A solver
that reports these as ordinary failures is hiding the real answer.
