#!/usr/bin/env python3
"""
Factory Steady-State solver.
Reads the JSON spec on STDIN, writes result JSON on STDOUT.

Approach
--------
• Build a linear-programming model (PuLP, open-source LGPL).
• Phase 1  – maximise scaling factor s ∈ [0,1] on the requested target rate.
          If optimal s < 1 – infeasible; report max rate = s*target.
• Phase 2  – lock s = 1 and minimise Σ machines_used, deterministic tie-break
          by adding a small ε*Σ recipe_flow to prefer lexicographic order.
All constraints obey 1e-9 tolerance.  The LP is small ( ≤ few hundred
variables) so CBC ships inside PuLP and meets the 2 s wall clock easily.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from typing import Dict, List

try:
    import pulp
except ImportError:  # graceful degradation
    sys.stderr.write(
        "ERROR: PuLP not installed – `pip install pulp` is required.\n"
    )
    sys.exit(1)

TOL = 1e-9


def effective_crafts_per_min(recipe: dict, machine: dict, module: dict | None) -> float:
    speed_bonus = module.get("speed", 0.0) if module else 0.0
    crafts = machine["crafts_per_min"] * (1 + speed_bonus) * 60 / recipe["time_s"]
    return crafts


def build_lp(data: dict, allow_scale: bool):
    recipes = data["recipes"]
    machines = data["machines"]
    modules = data.get("modules", {})
    raw_caps = data["limits"]["raw_supply_per_min"]
    max_machines = data["limits"]["max_machines"]
    target_item = data["target"]["item"]
    target_rate = data["target"]["rate_per_min"]

    # --------------------------------------------------------------------- #
    # VARIABLES
    # --------------------------------------------------------------------- #
    prob = pulp.LpProblem("factory", pulp.LpMaximize if allow_scale else pulp.LpMinimize)

    flow = {
        name: pulp.LpVariable(f"x_{name}", lowBound=0, cat="Continuous")
        for name in recipes
    }

    scale = (
        pulp.LpVariable("scale", lowBound=0, upBound=1, cat="Continuous")
        if allow_scale
        else None
    )

    # --------------------------------------------------------------------- #
    # EFFECTIVE RATES AND MACHINE USAGE
    # --------------------------------------------------------------------- #
    eff_rate: Dict[str, float] = {}
    machine_usage: Dict[str, List[pulp.LpAffineExpression]] = defaultdict(list)

    for rname, r in recipes.items():
        mtype = r["machine"]
        eff = effective_crafts_per_min(r, machines[mtype], modules.get(mtype, {}))
        eff_rate[rname] = eff
        machine_usage[mtype].append(flow[rname] / eff)

    # --------------------------------------------------------------------- #
    # CONSERVATION
    # --------------------------------------------------------------------- #
    # gather item sets
    produced = defaultdict(float)
    consumed = defaultdict(float)

    for rname, r in recipes.items():
        mtype = r["machine"]
        prod_bonus = modules.get(mtype, {}).get("prod", 0.0)
        for it, qty in r.get("out", {}).items():
            produced[it] += qty * (1 + prod_bonus) * flow[rname]
        for it, qty in r.get("in", {}).items():
            consumed[it] += qty * flow[rname]

    items = set(produced) | set(consumed) | {target_item} | set(raw_caps)

    for it in items:
        balance = produced[it] - consumed[it]
        if it == target_item:
            rhs = target_rate if scale is None else target_rate * scale
            prob += balance == rhs, f"balance_{it}"
        elif it in raw_caps:  # raw
            prob += balance <= TOL, f"raw_not_produced_{it}"
            prob += -balance <= raw_caps[it] + TOL, f"raw_cap_{it}"
        else:  # intermediate
            prob += balance == 0, f"balance_{it}"

    # --------------------------------------------------------------------- #
    # MACHINE CAPS
    # --------------------------------------------------------------------- #
    for mtype, terms in machine_usage.items():
        prob += pulp.lpSum(terms) <= max_machines[mtype] + TOL, f"cap_{mtype}"

    # --------------------------------------------------------------------- #
    # OBJECTIVE
    # --------------------------------------------------------------------- #
    if allow_scale:
        prob += scale
    else:
        # minimise total machines; tiny ε * Σ flow to break ties lexicographically
        eps = 1e-6
        obj = pulp.lpSum(
            machine_usage[mtype] for mtype in machine_usage
        ) + eps * pulp.lpSum(flow.values())
        prob += obj

    return prob, flow, scale, eff_rate


def solve_lp(prob: pulp.LpProblem):
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=1.8))
    return prob.status == pulp.LpStatusOptimal


def main():
    data = json.load(sys.stdin)

    # -------- Phase 1 – try with scaling factor -------------------------- #
    prob1, flow1, scale1, eff_rate1 = build_lp(data, allow_scale=True)
    feasible = solve_lp(prob1)

    if not feasible or scale1.varValue < 1 - 1e-6:
        max_rate = (scale1.varValue or 0.0) * data["target"]["rate_per_min"]
        hints = []

        # bottleneck identification: raw caps or machine caps tight within 1e-7
        for rcap in data["limits"]["raw_supply_per_min"]:
            lhs = -prob1.constraints[f"raw_cap_{rcap}"].value()
            if abs(lhs - data["limits"]["raw_supply_per_min"][rcap]) <= 1e-6:
                hints.append(f"{rcap} supply")

        for mtype in data["limits"]["max_machines"]:
            constr = prob1.constraints[f"cap_{mtype}"]
            used = constr.constant + constr.value()  # constant is <=0, value() negative
            if abs(used - data["limits"]["max_machines"][mtype]) <= 1e-6:
                hints.append(f"{mtype} cap")

        out = {
            "status": "infeasible",
            "max_feasible_target_per_min": round(max_rate, 6),
            "bottleneck_hint": sorted(set(hints))[:3] or ["unknown"],
        }
        print(json.dumps(out, separators=(",", ":")))
        return

    # -------- Phase 2 – minimise machines with s fixed at 1 --------------- #
    prob2, flow2, _, eff_rate2 = build_lp(data, allow_scale=False)
    # set initial solution as warm-start for determinism
    for fname, var in flow2.items():
        var.setInitialValue(flow1[fname].varValue)
        var.fixValue() if math.isclose(
            flow1[fname].varValue, 0.0, abs_tol=1e-9
        ) else None
    feasible2 = solve_lp(prob2)
    if not feasible2:
        # should not happen; fallback to phase1 solution
        chosen_flow = {k: v.varValue for k, v in flow1.items()}
    else:
        chosen_flow = {k: v.varValue for k, v in flow2.items()}

    # build per-machine counts and raw usage
    machine_counts = defaultdict(float)
    raw_usage = defaultdict(float)

    for rname, val in chosen_flow.items():
        r = data["recipes"][rname]
        mtype = r["machine"]
        eff = eff_rate2[rname]
        machine_counts[mtype] += val / eff
        for it, qty in r.get("in", {}).items():
            raw_usage[it] += qty * val

    # round small negatives
    chosen_flow = {k: max(0.0, round(v, 9)) for k, v in chosen_flow.items()}
    machine_counts = {k: round(v, 9) for k, v in machine_counts.items()}
    raw_usage = {k: round(v, 9) for k, v in raw_usage.items() if k in raw_usage}

    out = {
        "status": "ok",
        "per_recipe_crafts_per_min": dict(sorted(chosen_flow.items())),
        "per_machine_counts": dict(sorted(machine_counts.items())),
        "raw_consumption_per_min": dict(sorted(raw_usage.items())),
    }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
