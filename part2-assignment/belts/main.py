#!/usr/bin/env python3
"""
Bounded-belt max-flow with lower bounds and node caps.
Deterministic Dinic (BFS queue order alphabetical).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from typing import Dict, List, Tuple

INF = 10 ** 18
TOL = 1e-9


class Dinic:
    __slots__ = ("n", "adj", "level", "it")

    def __init__(self, n: int):
        self.n = n
        self.adj: List[List[Tuple[int, int, float]]] = [[] for _ in range(n)]
        # each edge: (to, rev_index, cap)

    def add_edge(self, fr: int, to: int, cap: float):
        fwd_idx = len(self.adj[fr])
        rev_idx = len(self.adj[to])
        self.adj[fr].append([to, rev_idx, cap])
        self.adj[to].append([fr, fwd_idx, 0.0])

    def bfs(self, s: int, t: int) -> bool:
        self.level = [-1] * self.n
        self.level[s] = 0
        q = deque([s])
        while q:
            v = q.popleft()
            for to, _, cap in sorted(self.adj[v], key=lambda x: x[0]):
                if cap > TOL and self.level[to] < 0:
                    self.level[to] = self.level[v] + 1
                    q.append(to)
        return self.level[t] >= 0

    def dfs(self, v: int, t: int, f: float) -> float:
        if v == t:
            return f
        for i in range(self.it[v], len(self.adj[v])):
            self.it[v] = i
            to, rev, cap = self.adj[v][i]
            if cap > TOL and self.level[v] + 1 == self.level[to]:
                ret = self.dfs(to, t, min(f, cap))
                if ret > 0:
                    self.adj[v][i][2] -= ret
                    self.adj[to][rev][2] += ret
                    return ret
        return 0.0

    def max_flow(self, s: int, t: int) -> float:
        flow = 0.0
        while self.bfs(s, t):
            self.it = [0] * self.n
            while True:
                f = self.dfs(s, t, INF)
                if f <= TOL:
                    break
                flow += f
        return flow

    def reachable(self, s: int) -> List[int]:
        seen = [False] * self.n
        stack = [s]
        while stack:
            v = stack.pop()
            if seen[v]:
                continue
            seen[v] = True
            for to, _, cap in self.adj[v]:
                if cap > TOL and not seen[to]:
                    stack.append(to)
        return [i for i, v in enumerate(seen) if v]


def main():
    data = json.load(sys.stdin)

    edges = data["edges"]  # list with from,to,lo,hi
    sources: Dict[str, float] = data["sources"]
    sink: str = data["sink"]
    caps: Dict[str, float] = data.get("caps", {})

    # node splitting ------------------------------------------------------ #
    idx: Dict[str, int] = {}
    counter = 0

    def get_idx(name: str, side: str = "") -> int:
        nonlocal counter
        key = f"{name}{side}"
        if key not in idx:
            idx[key] = counter
            counter += 1
        return idx[key]

    # create graphs
    g_edges = []

    for node, cap in caps.items():
        vin = f"{node}_in"
        vout = f"{node}_out"
        u = get_idx(vin)
        v = get_idx(vout)
        g_edges.append((vin, vout, 0.0, cap))

    # transfer original edges
    for e in edges:
        u = e["from"]
        v = e["to"]
        if u in caps:
            u = f"{u}_out"
        if v in caps:
            v = f"{v}_in"
        g_edges.append((u, v, e["lo"], e["hi"]))

    # connect sources
    for s, supply in sources.items():
        if s in caps:
            s = f"{s}_out"
        g_edges.append(("super_source", s, supply, supply))  # fixed supply as lo==hi

    super_sink_name = "super_sink"
    sink_node = sink if sink not in caps else f"{sink}_in"
    # sink demand edge: exact match
    g_edges.append((sink_node, super_sink_name, 0.0, sum(sources.values())))

    # assign indices for remaining
    for u, v, *_ in g_edges:
        get_idx(u)
        get_idx(v)
    S_star = get_idx("SS")
    T_star = get_idx("TT")

    dinic = Dinic(counter)

    # imbalances for lower-bound transform
    imbalance = [0.0] * counter

    for u_name, v_name, lo, hi in g_edges:
        u = idx[u_name]
        v = idx[v_name]
        dinic.add_edge(u, v, hi - lo)
        imbalance[u] -= lo
        imbalance[v] += lo

    # super-source/sink edges for feasibility
    demand_total = 0.0
    supply_total = 0.0
    for i, b in enumerate(imbalance):
        if b > TOL:
            dinic.add_edge(S_star, i, b)
            demand_total += b
        elif b < -TOL:
            dinic.add_edge(i, T_star, -b)
            supply_total += -b

    dinic.add_edge(idx[super_sink_name], idx["super_source"], INF)  # allow circulation

    feasible_flow = dinic.max_flow(S_star, T_star)

    if abs(feasible_flow - demand_total) > 1e-6:
        # infeasible – build min-cut
        reachable = dinic.reachable(S_star)
        cut_nodes = [n for n, i in idx.items() if i in reachable]
        deficit = demand_total - feasible_flow
        out = {
            "status": "infeasible",
            "cut_reachable": sorted(cut_nodes),
            "deficit": {
                "demand_balance": round(deficit, 6),
                "tight_nodes": [],
                "tight_edges": [],
            },
        }
        print(json.dumps(out, separators=(",", ":")))
        return

    # run real flow from original super_source to sink ------------------- #
    s_real = idx["super_source"]
    t_real = idx[super_sink_name]
    maxflow = dinic.max_flow(s_real, t_real)

    # reconstruct flows (add lo back)
    flows_out = []
    for u_name, v_name, lo, hi in g_edges:
        if u_name in ("super_source", super_sink_name) or v_name in (
            "super_source",
            super_sink_name,
        ):
            continue
        u = idx[u_name]
        v = idx[v_name]
        # residual reverse edge capacity gives flow
        rev = dinic.adj[v][dinic.adj[u][-1][1]]  # hack; last added from u->v
        flowed = dinic.adj[v][rev[1]][2]  # capacity on reverse
        flow_val = lo + flowed
        if flow_val > TOL:
            flows_out.append({"from": u_name.split("_")[0], "to": v_name.split("_")[0], "flow": round(flow_val, 9)})

    out = {
        "status": "ok",
        "max_flow_per_min": round(maxflow, 9),
        "flows": flows_out,
    }
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
