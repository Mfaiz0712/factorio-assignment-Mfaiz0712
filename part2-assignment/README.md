# Factorio Assignment – Design Notes

## A) Factory Steady-State

* **Modelling:**  One continuous LP, variables = crafts/min `x_r`.
  * Item balance rows enforce conservation exactly (`1e-9` tol).
  * Raw resources: non-positive net balance, upper-bounded by cap.
  * Machine caps: Σ `x_r / eff_rate_r` ≤ limit.
* **Modules:** speed & prod applied per machine-type before model build.
* **Cycles / by-products:** no special-case; balance rows cover them.
* **Feasibility:** maximise scale `s` ∈ [0,1] on target demand.If `s<1` → infeasible, report `s*target` and first 3 tight caps as hints.
* **Optimality:** fix `s=1`, minimise total machines; ε-weighted recipe sum
  gives deterministic lexicographic tie-break.
* **Solver:** PuLP + CBC (bundled, reproducible).

## B) Belts with Bounds

* **Node caps:** split `v`→`v_in → v_out` with cap edge.
* **Lower bounds:** subtract `lo`, accumulate imbalance vector.
* **Feasibility:** attach super-source/sink, run max-flow.Failure → reachable set + unused demand = certificate.
* **Final flow:** second max-flow from real super-source to super-sink,
  then add `lo` back to edge flows.
* **Algorithm:** deterministic Dinic (`O(E√V)` in practice).

## Numeric hygiene

Absolute tolerance `1e-9`; CBC time-limit 1.8 s per LP leaves headroom for
parsing.  All random generators seed with 0 for reproducibility.

## Edge-cases handled

* Degenerate recipes with zero IO – rejected by LP (0 throughput).
* Disconnected belt components – infeasible via unreachable sink.
* Machine or raw caps = 0 – still modelled, never divide by zero.

Happy grading! 🚀
