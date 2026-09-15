"""Runs every algorithm against every scenario and reports what each one did."""

import sys
import time
from pathlib import Path

# The domain packages live under src/, which is a source root rather than an
# installed package.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from algorithms.backtracker import BacktrackingSolver  # noqa: E402
from algorithms.graph_engine import GraphColouringSolver  # noqa: E402
from algorithms.greedy_solver import GreedySolver  # noqa: E402
from algorithms.instance import Instance  # noqa: E402
from algorithms.optimizer import Optimizer  # noqa: E402
from data.loader import available_scenarios, load_scenario  # noqa: E402

SOLVERS = (GreedySolver, BacktrackingSolver, GraphColouringSolver, Optimizer)


def main() -> None:
    results = {}

    for name in available_scenarios():
        instance = Instance.from_scenario(load_scenario(name))
        results[name] = []
        for solver_class in SOLVERS:
            # Nothing here knows which algorithm it is holding - every one of
            # them satisfies the same Solver protocol.
            solver = solver_class(instance)
            started = time.perf_counter()
            result = solver.solve()
            results[name].append((result, time.perf_counter() - started))

    print("coverage")
    header = f"{'scenario':<12}" + "".join(f"{s.name:>17}" for s in SOLVERS)
    print(header)
    print("-" * len(header))
    for name, runs in results.items():
        row = f"{name:<12}"
        for result, elapsed in runs:
            row += f"{result.coverage:>10.1%} {elapsed:>5.1f}s"
        print(row)

    print("\n\nconflict reports")
    for name, runs in results.items():
        best = max(runs, key=lambda r: r[0].coverage)[0]
        print(f"\n=== {name} (best: {best.solver}) ===")
        print(best.report())


if __name__ == "__main__":
    main()
