"""Runs Stages 1-4 on every scenario, prints the report figures and writes the conflict report."""

import sys
import time
from pathlib import Path

# Make the packages under src/ importable.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from algorithms.audit import audit
from algorithms.backtracker import BacktrackingSolver
from algorithms.graph_engine import GraphColouringSolver
from algorithms.greedy_solver import GreedySolver
from algorithms.instance import Instance
from algorithms.optimizer import RoomAllocator
from data.loader import available_scenarios, load_scenario

COLUMNS = ("greedy", "graph-welsh-powell", "dp-rooms", "backtracking")
REPORT_PATH = Path(__file__).parent / "reports" / "conflict_report.txt"


def timed(run):
    """Call `run()` and return (its result, seconds taken)."""
    started = time.perf_counter()
    result = run()
    return result, time.perf_counter() - started


def run_scenario(instance):
    """Run every stage on one instance.

    Returns:
        ({stage name: (result, seconds)}, the Stage 2 slot map).
    """
    colouring = GraphColouringSolver(instance)
    coloured = timed(colouring.solve)
    runs = {
        "greedy": timed(GreedySolver(instance).solve),
        "graph-welsh-powell": coloured,
        # Stage 3 keeps the Stage 2 time slots.
        "dp-rooms": timed(lambda: RoomAllocator(instance).allocate(coloured[0])),
        "backtracking": timed(BacktrackingSolver(instance).solve),
    }
    return runs, colouring.slot_map


def heading(text):
    """Print a section heading."""
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def main() -> None:
    """Run all scenarios, print each report section and write the conflict report."""
    results = {}
    slot_maps = {}
    instances = {}
    heading("Scenarios")
    for name in available_scenarios():
        scenario = load_scenario(name)
        instance = instances[name] = Instance.from_scenario(scenario)
        results[name], slot_maps[name] = run_scenario(instance)
        students = f"{scenario.students:,} students" if scenario.students else "students n/a"
        print(f"{name:<12}{students:>16}, {len(scenario.professors):>3} professors, "
              f"{len(scenario.rooms):>2} rooms, {len(scenario.classes):>3} classes, "
              f"{len(scenario.groups):>3} student groups")

    heading("Constraint audit - every final schedule checked against goals 1-4")
    for name, runs in results.items():
        print(f"\n{name}")
        for column in COLUMNS:
            print(f"  {column:<20} {audit(runs[column][0].assignments, instances[name]).summary()}")

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

    write_conflict_report(results, instances, REPORT_PATH)
    print(f"\nFull conflict report written to {REPORT_PATH.relative_to(Path(__file__).parent)}")


def write_conflict_report(results, instances, path: Path) -> None:
    """Write the Stage 4 result of every scenario, listing every unplaced class, to `path`."""
    lines = [
        "CONFLICT REPORT",
        "Final schedule per scenario: Stage 4 (backtracking, best effort).",
        "Every class that could not be placed is listed with its cause, and the",
        "schedule is audited against goals 1-4 (see src/domains/constraints.py).",
    ]
    for name, runs in results.items():
        result = runs["backtracking"][0]
        lines += [
            "",
            "=" * 78,
            f"{name}",
            "=" * 78,
            f"audit: {audit(result.assignments, instances[name]).summary()}",
            "",
            result.report(examples=len(result.conflicts)),
            "",
            result.manual_intervention_report(),
        ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _change(before: int, after: int) -> str:
    """Relative change from `before` to `after`, as a signed percentage."""
    return f"{(after - before) / before:+.1%}" if before else "-"


if __name__ == "__main__":
    main()
