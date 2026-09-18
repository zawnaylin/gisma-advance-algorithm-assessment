"""Runs the four stages against every scenario and prints what each report needs.

Stage 1  greedy baseline
Stage 2  graph colouring (Welsh-Powell) and the safe/unsafe slot map
Stage 3  dynamic-programming room allocation on the Stage 2 time slots
Stage 4  backtracking, best effort, and the manual-intervention list
"""

import sys
import time
from pathlib import Path

# The domain packages live under src/, which is a source root rather than an
# installed package.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from algorithms.backtracker import BacktrackingSolver
from algorithms.graph_engine import GraphColouringSolver
from algorithms.greedy_solver import GreedySolver
from algorithms.instance import Instance
from algorithms.room_allocator import RoomAllocator
from data.loader import available_scenarios, load_scenario

COLUMNS = ("greedy", "graph-welsh-powell", "dp-rooms", "backtracking")


def timed(run):
    started = time.perf_counter()
    result = run()
    return result, time.perf_counter() - started


def run_scenario(instance):
    colouring = GraphColouringSolver(instance)
    runs = {
        "greedy": timed(GreedySolver(instance).solve),
        "graph-welsh-powell": timed(colouring.solve),
        "dp-rooms": timed(lambda: RoomAllocator(instance).allocate(runs["graph-welsh-powell"][0])),
        "backtracking": timed(BacktrackingSolver(instance).solve)
    }
    return runs, colouring.slot_map


def heading(text):
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def main() -> None:
    results = {}
    slot_maps = {}
    for name in available_scenarios():
        instance = Instance.from_scenario(load_scenario(name))
        results[name], slot_maps[name] = run_scenario(instance)

    heading("Coverage - share of the classes placed (time in seconds)")
    print(f"{'scenario':<12}" + "".join(f"{c:>20}" for c in COLUMNS))
    for name, runs in results.items():
        row = f"{name:<12}"
        for column in COLUMNS:
            result, elapsed = runs[column]
            row += f"{result.coverage:>13.1%} {elapsed:>5.2f}s"
        print(row)

    heading("Stage 2 - greedy vs graph colouring: unplaced classes by cause")
    for name, runs in results.items():
        print(f"\n{name}")
        for column in ("greedy", "graph-welsh-powell"):
            result = runs[column][0]
            causes = ", ".join(f"{c}={len(v)}" for c, v in result.conflicts_by_cause().items())
            print(f"  {column:<20} {len(result.conflicts):>3} unplaced  {causes or '-'}")
        print(f"  slot map: {slot_maps[name].summary()}")

    heading("Stage 2 - safe / unsafe slot map, cohorts   (# own slot, . safe, x unsafe)")
    if "cohorts" in slot_maps:
        slot_map = slot_maps["cohorts"]
        tightest_placed = min(slot_map.assigned, key=lambda cid: (slot_map.safe_count(cid), cid))
        boxed_in = slot_map.without_safe_slot()
        for label, class_id in (("placed", tightest_placed), ("unplaced", boxed_in[0] if boxed_in else None)):
            if class_id is None:
                continue
            print(f"\n{label} class {class_id}: {slot_map.safe_count(class_id)} safe, "
                  f"{slot_map.unsafe_count(class_id)} unsafe windows")
            print(slot_map.render(class_id))

    heading("Stage 3 - wasted seats (empty seats summed over every placement)")
    print(f"{'scenario':<12}{'greedy':>10}{'stage 2 rooms':>15}{'dp-rooms':>10}"
          f"{'dp vs stage 2':>15}{'dp vs greedy':>14}")
    for name, runs in results.items():
        greedy = runs["greedy"][0].wasted_seats
        provisional = runs["graph-welsh-powell"][0].wasted_seats
        dp = runs["dp-rooms"][0].wasted_seats
        print(f"{name:<12}{greedy:>10}{provisional:>15}{dp:>10}"
              f"{_change(provisional, dp):>15}{_change(greedy, dp):>14}")

    heading("Stage 4 - backtracking, best effort")
    for name, runs in results.items():
        result = runs["backtracking"][0]
        print(f"\n=== {name} ===")
        print(result.report())
        print(result.manual_intervention_report())


def _change(before: int, after: int) -> str:
    return f"{(after - before) / before:+.1%}" if before else "-"


if __name__ == "__main__":
    main()
