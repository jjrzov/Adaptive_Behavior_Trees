import csv
from collections import defaultdict

SPREAD_BUCKETS = [(0, 10), (11, 20), (21, 40), (41, 999)]


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            r["spread"] = int(r["spread"])
            r["min"] = int(r["min"])
            r["node_count"] = int(r["node_count"]) if r["node_count"] else None
            r["expansions"] = int(r["expansions"])
            r["solved"] = r["solved"] == "True"
            rows.append(r)
    return rows


def summarize(rows):
    arms = sorted({r["arm"] for r in rows})

    for lo, hi in SPREAD_BUCKETS:
        sel = [r for r in rows if lo <= r["spread"] <= hi and r["solved"]]
        if not sel:
            continue
        print(f"\nspread {lo}-{hi}   (n={len(sel)//len(arms)} problems)")
        print(f"  {'arm':<15} {'nodes':>8} {'expansions':>12} {'cheapest %':>12}")
        for arm in arms:
            a = [r for r in sel if r["arm"] == arm]
            if not a:
                continue
            nodes = [r["node_count"] for r in a if r["node_count"] is not None]
            exps = [r["expansions"] for r in a]
            picked = [r for r in a if r.get("picked_cheapest") == "True"]
            print(f"  {arm:<15} {sum(nodes)/len(nodes):>8.1f} "
                  f"{sum(exps)/len(exps):>12.1f} "
                  f"{100*len(picked)/len(a):>11.1f}%")


def paired(rows, baseline="BFS"):
    # per-problem deltas against the baseline arm
    by_problem = defaultdict(dict)
    for r in rows:
        if r["solved"]:
            by_problem[r["problem_id"]][r["arm"]] = r

    arms = sorted({r["arm"] for r in rows}) 
    print("\npaired vs", baseline)
    for arm in arms:
        if arm == baseline:
            continue
        wins = losses = ties = 0
        for p in by_problem.values():
            if arm in p and baseline in p:
                a, b = p[arm]["node_count"], p[baseline]["node_count"]
                if a < b: wins += 1
                elif a > b: losses += 1
                else: ties += 1
        print(f"  {arm}: smaller {wins}, larger {losses}, tied {ties}")

        ratios = [p[arm]["node_count"] / p[baseline]["node_count"]
        for p in by_problem.values()
        if arm in p and baseline in p and p[baseline]["node_count"]]
        if ratios:
            print(f"    node ratio: mean {sum(ratios)/len(ratios):.2f}, "
                  f"range {min(ratios):.2f}-{max(ratios):.2f}")


if __name__ == "__main__":
    rows = load("or_sweep.csv")
    summarize(rows)
    paired(rows)