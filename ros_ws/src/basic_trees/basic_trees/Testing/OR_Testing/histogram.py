import random
import math
import matplotlib.pyplot as plt
from collections import Counter

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution, getDisjunctSets

TARGET_SUCCESSES = 500


def recordData(case):
    invalid = 0 # Count for amount of times a valid state cannot be found
    infs = 0
    runs = []  # Run for 500 trees


    while len(runs) < TARGET_SUCCESSES:
        all_literals = generateLiterals(case["literals"])
        states_database, action_database = generateSolution(
            all_literals, case["distance"], case["iterations"]
        )
 
        # Record data
        sample = getDisjunctSets(states_database, action_database)
        if (sample == None):
            invalid += 1
            continue

        _, _, dist1, dist2 = sample
        if dist1 == math.inf or dist2 == math.inf:
            infs += 1
        else:
            hi, lo = max(dist1, dist2), min(dist1, dist2)
            runs.append({"min": lo, "max": hi, "spread": hi - lo, "ratio": (hi - lo) / hi})

        # if len(runs) % 50 == 0:
        #     print(f"   Case {case['case']}: {len(runs)}/{TARGET_SUCCESSES} successes")

    return runs, invalid, infs


def plotSpread(runs, case):
    spreads = [r["spread"] for r in runs]

    counts = Counter(spreads)
    print(f"n = {len(spreads)}")
    for s in sorted(counts):
        print(f"  spread {s:>3}: {counts[s]:>4}  ({counts[s]/len(spreads):.1%})")

    fig, ax = plt.subplots(figsize=(8, 5))
    bins = range(0, max(spreads) + 2)
    ax.hist(spreads, bins=bins, align="left", edgecolor="black")
    ax.set_xlabel("spread (max disjunct distance − min)")
    ax.set_ylabel("problems")
    ax.set_title(
        f"Disjunct distance spread — literals={case['literals']}, "
        f"distance={case['distance']}, iterations={case['iterations']}"
    )
    ax.set_xticks(list(bins)[:-1])
    fig.tight_layout()
    fig.savefig("spread_histogram.png", dpi=150)
    plt.close(fig)


def main():
    test_case = {"case": 1, "literals": 100, "distance": 100, "iterations": 10}

    runs, invalid, infs = recordData(test_case)

    print(f"literals = {test_case['literals']}, distance = {test_case['distance']}, iterations = {test_case['iterations']}")

    plotSpread(runs, test_case)

    buckets = [(1, 10), (11, 20), (21, 30), (31, 999)]
    print("\n  spread bucket |   n | min: mean (range)")
    for lo, hi in buckets:
        sel = [r["min"] for r in runs if lo <= r["spread"] <= hi]
        if sel:
            print(f"  {lo:>3}-{hi:<3}      | {len(sel):>3} | {sum(sel)/len(sel):>5.1f} ({min(sel)}-{max(sel)})")


    ratio_buckets = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]
    print("\n  ratio bucket |   n | min: mean (range)")
    for lo, hi in ratio_buckets:
        sel = [r["min"] for r in runs if lo <= r["ratio"] < hi]
        if sel:
            print(f"  {lo:.2f}-{hi:.2f}   | {len(sel):>3} | {sum(sel)/len(sel):>5.1f} ({min(sel)}-{max(sel)})")

    print(f"invalid: {invalid}")
    print(f"infinites: {infs}")



if __name__ == '__main__':
    main()