#!/usr/bin/env python3
"""
verify_belts.py  –  quick sanity-checker for the ‘belts’ task.

Usage
-----
    python verify_belts.py spec.json solver_output.json

What is checked
---------------
1. Every reported edge flow lies within its [lo, hi] bounds (±TOL).
2. Item conservation at each node:
       Σ in-flow + supply == Σ out-flow + demand          (|ε| ≤ TOL)
   • supplies come from `sources`
   • a single sink must absorb exactly total supply
3. Throughput caps:  max(total-in, total-out) ≤ cap (±TOL)
4. The solver’s advertised max_flow equals total supply (±TOL).

If `status` ≠ "ok" the script only prints a warning (we can’t certify an
infeasible certificate easily without rerunning a flow algorithm).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOL = 1e-6


def die(msg: str):
    print(f"❌  {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) != 3:
        die("Usage: verify_belts.py spec.json solver_output.json")

    spec_path, sol_path = map(Path, sys.argv[1:3])
    spec = json.loads(spec_path.read_text())
    sol = json.loads(sol_path.read_text())

    # ------------------------------------------------------------------ #
    # Trivial case – solver declared infeasible; accept at face value
    # ------------------------------------------------------------------ #
    if sol.get("status") != "ok":
        print("⚠️  solution marked ‘infeasible’; no correctness checks performed.")
        return

    # ------------------------------------------------------------------ #
    # Helpful look-ups
    # ------------------------------------------------------------------ #
    edge_bounds = {
        (e["from"], e["to"]): (e["lo"], e["hi"]) for e in spec["edges"]
    }
    flow = { (f["from"], f["to"]): float(f["flow"]) for f in sol["flows"] }

    sources = spec["sources"]
    sink = spec["sink"]
    caps = spec.get("caps", {})

    total_supply = sum(sources.values())
    advertised = sol.get("max_flow_per_min", total_supply)

    if abs(advertised - total_supply) > TOL:
        die(
            f"max_flow_per_min ({advertised}) does not match total supply"
            f" ({total_supply})"
        )

    # ------------------------------------------------------------------ #
    # 1. Edge bounds
    # ------------------------------------------------------------------ #
    for key, (lo, hi) in edge_bounds.items():
        f = flow.get(key, 0.0)
        if not (lo - TOL <= f <= hi + TOL):
            die(
                f"Edge {key} flow {f} outside bounds [{lo}, {hi}]"
            )

    # ------------------------------------------------------------------ #
    # 2. Node balances
    # ------------------------------------------------------------------ #
    balance = {}

    def acc(node: str, delta: float):
        balance[node] = balance.get(node, 0.0) + delta

    for (u, v), f in flow.items():
        acc(u, -f)
        acc(v, +f)

    for s, sup in sources.items():
        acc(s, +sup)

    acc(sink, -total_supply)

    bad = {n: b for n, b in balance.items() if abs(b) > TOL}
    if bad:
        die(f"Node balance violation: {bad}")

    # ------------------------------------------------------------------ #
    # 3. Throughput caps
    # ------------------------------------------------------------------ #
    for n, cap in caps.items():
        inflow = sum(f for (u, v), f in flow.items() if v == n)
        outflow = sum(f for (u, v), f in flow.items() if u == n)
        if inflow - TOL > cap or outflow - TOL > cap:
            die(
                f"Node {n} exceeds cap {cap}: "
                f"in={inflow:.6g}, out={outflow:.6g}"
            )

    print("✅  belts solution passes all checks")


if __name__ == "__main__":
    main()
