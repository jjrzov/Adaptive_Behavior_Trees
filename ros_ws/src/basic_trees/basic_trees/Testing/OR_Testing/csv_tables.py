import csv
from collections import defaultdict
from statistics import mean


N_BUCKETS = 4   # spread buckets, derived from the data rather than hardcoded


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            r["spread"] = float(r["spread"])
            r["min"] = float(r["min"])
            r["max"] = float(r["max"])
            r["hops1"] = int(r["hops1"]) if r["hops1"] else None
            r["hops2"] = int(r["hops2"]) if r["hops2"] else None
            r["agree"] = r["agree"] == "True"
            r["dist1"] = float(r["dist1"])
            r["dist2"] = float(r["dist2"])
            r["node_count"] = int(r["node_count"]) if r["node_count"] else None
            r["expansions"] = int(r["expansions"])
            r["solved"] = r["solved"] == "True"
            rows.append(r)
    return rows


def makeBuckets(rows, n=N_BUCKETS):
    # Quantile edges over the observed spreads, so buckets hold roughly equal counts
    spreads = sorted({(r["problem_id"], r["spread"]) for r in rows})
    values = sorted(s for _, s in spreads)
    if not values:
        return []

    edges = [values[int(i * len(values) / n)] for i in range(n)]
    edges.append(float("inf"))
    return [(edges[i], edges[i + 1]) for i in range(n)]


def describeSpread(rows):
    per_problem = {r["problem_id"]: r["spread"] for r in rows}
    vals = sorted(per_problem.values())
    if not vals:
        return
    print(f"spread over {len(vals)} problems: "
          f"min {vals[0]:.1f}, median {vals[len(vals)//2]:.1f}, max {vals[-1]:.1f}")


def summarize(rows, buckets):
    arms = sorted({r["arm"] for r in rows})

    for lo, hi in buckets:
        sel = [r for r in rows if lo <= r["spread"] < hi and r["solved"]]
        if not sel:
            continue
        n_problems = len({r["problem_id"] for r in sel})
        print(f"\nspread {lo:.1f}-{hi:.1f}   (n={n_problems} problems)")
        print(f"  {'arm':<15} {'nodes':>8} {'expansions':>12} {'cheapest %':>12}")

        for arm in arms:
            a = [r for r in sel if r["arm"] == arm]
            if not a:
                continue
            nodes = [r["node_count"] for r in a if r["node_count"] is not None]
            exps = [r["expansions"] for r in a]

            # Only rows that report a choice count toward the rate (DNF does not)
            judged = [r for r in a if r.get("disjunct_reached")]
            picked = [r for r in judged if r.get("picked_cheapest") == "True"]
            rate = f"{100*len(picked)/len(judged):>11.1f}%" if judged else f"{'-':>12}"

            print(f"  {arm:<15} {mean(nodes):>8.1f} {mean(exps):>12.1f} {rate}")


def paired(rows, metric, baseline="BFS"):
    # Per-problem comparison against the baseline arm, on one metric
    by_problem = defaultdict(dict)
    for r in rows:
        if r["solved"] and r[metric] is not None:
            by_problem[r["problem_id"]][r["arm"]] = r

    arms = sorted({r["arm"] for r in rows})
    print(f"\npaired {metric} vs {baseline}")

    for arm in arms:
        if arm == baseline:
            continue

        pairs = [(p[arm][metric], p[baseline][metric])
                 for p in by_problem.values()
                 if arm in p and baseline in p]
        if not pairs:
            continue

        wins = sum(1 for a, b in pairs if a < b)
        losses = sum(1 for a, b in pairs if a > b)
        ties = len(pairs) - wins - losses

        ratios = [a / b for a, b in pairs if b]
        print(f"  {arm:<15} smaller {wins}, larger {losses}, tied {ties}")
        if ratios:
            print(f"  {'':<15} ratio: mean {mean(ratios):.2f}, "
                  f"range {min(ratios):.2f}-{max(ratios):.2f}")


def tradeoff(rows):
    # The comparison that matters: expansion cost against how often the choice was right
    arms = sorted({r["arm"] for r in rows})
    print(f"\noverall   {'arm':<15} {'expansions':>12} {'nodes':>8} {'cheapest %':>12} {'solved %':>10}")

    for arm in arms:
        a = [r for r in rows if r["arm"] == arm]
        if not a:
            continue
        solved = [r for r in a if r["solved"]]
        exps = [r["expansions"] for r in solved]
        nodes = [r["node_count"] for r in solved if r["node_count"] is not None]

        judged = [r for r in solved if r.get("disjunct_reached")]
        picked = [r for r in judged if r.get("picked_cheapest") == "True"]
        rate = f"{100*len(picked)/len(judged):>11.1f}%" if judged else f"{'-':>12}"

        print(f"          {arm:<15} {mean(exps):>12.1f} {mean(nodes):>8.1f} "
              f"{rate} {100*len(solved)/len(a):>9.1f}%")


def describeAgreement(rows):
    per_problem = {r["problem_id"]: r["agree"] for r in rows}
    n = len(per_problem)
    agreed = sum(1 for v in per_problem.values() if v)
    print(f"cost and hop count agree on {agreed}/{n} problems ({100*agreed/n:.0f}%)")


def describeHops(rows):
    per_problem = {}
    for r in rows:
        if r["hops1"] is not None:
            per_problem[r["problem_id"]] = (r["hops1"], r["hops2"], r["agree"])

    gaps = [abs(h1 - h2) for h1, h2, _ in per_problem.values()]
    gaps.sort()
    n = len(gaps)

    print(f"\nhop gap |hops1 - hops2| over {n} problems:")
    print(f"  min {gaps[0]}, median {gaps[n//2]}, max {gaps[-1]}")

    for k in (0, 1, 2, 3, 5):
        close = [(h1, h2, a) for h1, h2, a in per_problem.values() if abs(h1 - h2) <= k]
        if not close:
            print(f"  gap <= {k}: 0 problems")
            continue
        agreed = sum(1 for _, _, a in close if a)
        print(f"  gap <= {k}: {len(close):>4} problems, "
              f"cost/hops agree {agreed}/{len(close)} ({100*agreed/len(close):.0f}%)")


def describeRatios(rows, n=15):
    seen = {}
    for r in rows:
        if r["hops1"] and r["problem_id"] not in seen:
            seen[r["problem_id"]] = r

    print(f"\ncost per hop (first {n} problems):")
    print(f"  {'dist1':>10} {'hops1':>6} {'ratio':>9}   {'dist2':>10} {'hops2':>6} {'ratio':>9}")

    ratios = []
    for r in list(seen.values())[:n]:
        r1 = r["dist1"] / r["hops1"]
        r2 = r["dist2"] / r["hops2"]
        print(f"  {r['dist1']:>10.1f} {r['hops1']:>6} {r1:>9.1f}   "
              f"{r['dist2']:>10.1f} {r['hops2']:>6} {r2:>9.1f}")

    for r in seen.values():
        ratios.append(r["dist1"] / r["hops1"])
        ratios.append(r["dist2"] / r["hops2"])
    ratios.sort()
    print(f"  across all: min {ratios[0]:.1f}, "
          f"median {ratios[len(ratios)//2]:.1f}, max {ratios[-1]:.1f}")


if __name__ == "__main__":
    rows = load("or_sweep.csv")

    # describeSpread(rows)
    # describeAgreement(rows)
    # describeHops(rows)
    # describeRatios(rows)

    tradeoff(rows)

    buckets = makeBuckets(rows)
    summarize(rows, buckets)

    paired(rows, "node_count")
    paired(rows, "expansions")