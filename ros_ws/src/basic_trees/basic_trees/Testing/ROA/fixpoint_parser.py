'''
Summarizes the ROA comparison CSV: correctness checks first, then the claims.
'''
import csv
import statistics as stats


def loadRows(path):
    with open(path, newline="") as f:
        return [{k: int(v) for k, v in row.items()} for row in csv.DictReader(f)]


def summarize(path):
    rows = loadRows(path)
    n = len(rows)

    # --- Validity checks: these must all be zero before anything else matters
    # violations = sum(r["u_violations"] + r["d_violations"] for r in rows)

    fs = sum(r["u_false_success"] + r["d_false_success"] for r in rows)
    print(f"false-success ticks: {fs}")
    print(f"unrecovered violations: {sum(r['u_violations'] + r['d_violations'] for r in rows)}")

    unified_only = sum(r["unified_only"] for r in rows)
    bad = [r["problem_id"] for r in rows
           if r["u_violations"] or r["d_violations"] or r["unified_only"]]

    print(f"problems: {n}")
    # print(f"violations (must be 0): {violations}")
    print(f"unified_only total (must be 0): {unified_only}")
    if bad:
        print(f"  problems to inspect: {bad[:10]}")

    # --- ROA preservation
    gaps = [r["dnf_only"] for r in rows]
    mismatched = [r["problem_id"] for r in rows if r["dnf_only"]]
    covered = sum(r["both"] for r in rows)
    reachable = sum(r["both"] + r["dnf_only"] for r in rows)

    print(f"\nproblems with identical ROA: {sum(g == 0 for g in gaps)}/{n}")
    print(f"states only DNF solves: {sum(gaps)} of {reachable} "
          f"({100 * covered / reachable:.1f}% preserved)" if reachable else "")
    if mismatched:
        print(f"  problems with a gap: {mismatched[:10]}")

    # --- Size
    node_ratio = [r["d_nodes"] / r["u_nodes"] for r in rows if r["u_nodes"]]
    exp_ratio = [r["d_expansions"] / r["u_expansions"] for r in rows if r["u_expansions"]]
    u_dup = [r["u_conditions"] / r["u_unique"] for r in rows if r["u_unique"]]
    d_dup = [r["d_conditions"] / r["d_unique"] for r in rows if r["d_unique"]]

    for label, vals in [("DNF/unified nodes", node_ratio),
                        ("DNF/unified expansions", exp_ratio),
                        ("unified duplication", u_dup),
                        ("DNF duplication", d_dup)]:
        if vals:
            sd = stats.stdev(vals) if len(vals) > 1 else 0.0
            print(f"{label}: mean {stats.mean(vals):.2f}, sd {sd:.2f}, "
                  f"min {min(vals):.2f}, max {max(vals):.2f}")

    # --- Cycles: should be 0 on flat goals
    print(f"\ncycles: unified {sum(r['u_cycles'] for r in rows)}, "
          f"dnf {sum(r['d_cycles'] for r in rows)}")

    # --- Shared
    shared = [r["shared"] for r in rows]
    resid = [r["r1"] + r["r2"] for r in rows]
    print(f"\nshared literals: mean {stats.mean(shared):.1f}, "
          f"zero-overlap problems: {sum(s == 0 for s in shared)}/{n}")
    print(f"residual literals: mean {stats.mean(resid):.1f}")
    print(f"caps (must be 0): {sum(r['caps'] for r in rows)}")

if __name__ == "__main__":
    summarize("roa_nested.csv")