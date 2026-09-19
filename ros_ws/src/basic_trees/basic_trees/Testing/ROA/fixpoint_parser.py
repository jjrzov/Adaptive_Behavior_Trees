'''
Summarizes the ROA comparison CSV: validity checks first, then the claims.
'''
import csv
import statistics as stats


def loadRows(path):
    def conv(v):
        return float(v) if "." in v else int(v)

    with open(path, newline="") as f:
        return [{k: conv(v) for k, v in row.items()} for row in csv.DictReader(f)]


def ratios(rows, num, den):
    # Per-problem ratio, skipping rows with a zero denominator
    return [r[num] / r[den] for r in rows if r[den]]


def describe(label, vals):
    if not vals:
        return
    sd = stats.stdev(vals) if len(vals) > 1 else 0.0
    print(f"  {label}: mean {stats.mean(vals):.2f}, sd {sd:.2f}, "
          f"min {min(vals):.2f}, max {max(vals):.2f}")


def corr(xs, ys):
    # Undefined when either variable is constant
    if len(xs) < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    return stats.correlation(xs, ys)


def reportValidity(rows):
    # Nothing below this is meaningful until these are clean
    print("VALIDITY")
    print(f"  problems: {len(rows)}")
    print(f"  false-success ticks: {sum(r['u_false_success'] + r['d_false_success'] for r in rows)}")
    print(f"  unrecovered violations: {sum(r['u_violations'] + r['d_violations'] for r in rows)}")
    print(f"  unified_only (expect 0): {sum(r['unified_only'] for r in rows)}")
    print(f"  caps (expect 0): {sum(r['caps'] for r in rows)}")
    print(f"  cycles: unified {sum(r['u_cycles'] for r in rows)}, "
          f"dnf {sum(r['d_cycles'] for r in rows)}")

    suspect = [r["problem_id"] for r in rows if r["unified_only"] or r["caps"]]
    if suspect:
        print(f"  problems to inspect: {suspect[:10]}")


def reportROA(rows):
    # DNF at fixpoint is the ceiling, so dnf_only is the whole gap
    reachable = sum(r["both"] + r["dnf_only"] for r in rows)
    if not reachable:
        print("\nROA: no reachable states in any problem")
        return

    covered = sum(r["both"] for r in rows)
    identical = sum(1 for r in rows if r["dnf_only"] == 0)
    gap_problems = [r["problem_id"] for r in rows if r["dnf_only"]]

    print("\nROA PRESERVATION")
    print(f"  identical ROA: {identical}/{len(rows)} problems")
    print(f"  states preserved: {covered}/{reachable} ({100 * covered / reachable:.1f}%)")
    if gap_problems:
        print(f"  problems with a gap: {gap_problems[:10]}")


def reportSize(rows):
    print("\nSIZE")
    describe("DNF/unified nodes", ratios(rows, "d_nodes", "u_nodes"))
    describe("DNF/unified expansions", ratios(rows, "d_expansions", "u_expansions"))
    describe("unified duplication", ratios(rows, "u_conditions", "u_unique"))
    describe("DNF duplication", ratios(rows, "d_conditions", "d_unique"))

    # DNF expands unreachable disjuncts too, which inflates its node count
    full = [r for r in rows if r["n_solvable"] == r["n_disjuncts"]]
    part = [r for r in rows if r["n_solvable"] < r["n_disjuncts"]]

    for label, group in [("all disjuncts solvable", full), ("some unsolvable", part)]:
        vals = ratios(group, "d_nodes", "u_nodes")
        if vals:
            print(f"  {label}: {len(group)}/{len(rows)} problems, "
                  f"node ratio {stats.mean(vals):.2f}")


def reportGoalShape(rows):
    # Does sharing more of the goal make the unified tree relatively smaller?
    print("\nGOAL SHAPE")
    shared = [r["shared"] for r in rows]
    print(f"  shared literals: mean {stats.mean(shared):.1f}, "
          f"zero-overlap: {sum(s == 0 for s in shared)}/{len(rows)}")
    print(f"  residual literals: mean {stats.mean([r['r1'] + r['r2'] for r in rows]):.1f}")
    print(f"  disjuncts: mean {stats.mean([r['n_disjuncts'] for r in rows]):.1f}")

    usable = [r for r in rows if r["u_nodes"] and (r["shared"] + r["r1"] + r["r2"])]
    xs = [r["shared"] / (r["shared"] + r["r1"] + r["r2"]) for r in usable]
    ys = [r["d_nodes"] / r["u_nodes"] for r in usable]

    if xs:
        print(f"  overlap fraction: mean {stats.mean(xs):.2f}, "
              f"range {min(xs):.2f}-{max(xs):.2f}")
    c = corr(xs, ys)
    if c is not None:
        print(f"  corr(overlap, node ratio) = {c:.2f}")


def reportInterference(rows):
    # Static conflicts: actions in an OR branch that can break a shared literal
    print("\nINTERFERENCE")
    br = ratios(rows, "branch_conflict", "branch_actions")
    db = ratios(rows, "db_conflict", "db_actions")

    if br:
        print(f"  conflicting actions in OR branches: mean {stats.mean(br):.2f}")
    if db:
        print(f"  conflicting actions in the domain: mean {stats.mean(db):.2f}")
    print(f"  problems with at least one conflict: "
          f"{sum(1 for r in rows if r['branch_conflict'])}/{len(rows)}")
    print(f"  mean del-set size: {stats.mean([r['mean_del'] for r in rows]):.1f}")

    usable = [r for r in rows if r["branch_actions"]]
    c = corr([r["branch_conflict"] / r["branch_actions"] for r in usable],
             [r["dnf_only"] for r in usable])
    if c is not None:
        print(f"  corr(conflict rate, dnf_only) = {c:.2f}")


def reportSweep(rows):
    # Only meaningful when the run varied interference across problems
    by_p = {}
    for r in rows:
        by_p.setdefault(r["interfere_p"], []).append(r)

    if len(by_p) < 2:
        return

    print("\nBY INTERFERENCE")
    print(f"  {'p':>5} {'n':>4} {'states':>7} {'preserved':>10} {'nodes d/u':>10} {'conflict':>9}")

    for p in sorted(by_p):
        group = by_p[p]
        reachable = sum(r["both"] + r["dnf_only"] for r in group)
        if not reachable:
            print(f"  {p:>5.1f} {len(group):>4} {0:>7}  (no reachable states)")
            continue

        preserved = sum(r["both"] for r in group) / reachable
        node = stats.mean(ratios(group, "d_nodes", "u_nodes"))
        conflict = stats.mean(ratios(group, "branch_conflict", "branch_actions") or [0])

        print(f"  {p:>5.1f} {len(group):>4} {reachable:>7} {preserved:>9.1%} "
              f"{node:>10.2f} {conflict:>9.2f}")


def summarize(path):
    rows = loadRows(path)
    if not rows:
        print(f"no rows in {path}")
        return

    # Problems where neither arm solves anything say nothing about the comparison
    live = [r for r in rows if r["both"] + r["dnf_only"] > 0]
    degenerate = len(rows) - len(live)

    reportValidity(rows)
    if degenerate:
        print(f"  degenerate problems excluded below: {degenerate}/{len(rows)} "
              f"(empty ROA on both arms)")

    if not live:
        print("\nNo informative problems.")
        return

    reportROA(live)
    reportSize(live)
    reportGoalShape(live)
    reportInterference(live)
    reportSweep(live)


if __name__ == "__main__":
    summarize("roa_nav.csv")