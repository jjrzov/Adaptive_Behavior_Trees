'''
Statistics for the scoped vs global expansion comparison.

Reads the CSVs written by pruning_scope_roa.py and prints every value quoted
in the thesis subsection, together with the rows of its table in LaTeX.

    python pruning_stats.py --nested pruning_nested_minimal.csv \\
                            --deep pruning_deep_minimal.csv \\
                            --flat pruning_flat_minimal.csv

Intervals are 95% intervals from resampling whole problems. The resampling
follows soundness_plots.py exactly (one stream seeded with 0, arms in the same
order, the same statistic), so the scoped rows reproduce the intervals of the
soundness figure and table digit for digit.
'''
import argparse
import csv
import math
import random


BOOTSTRAP = 2000
LO, HI = int(0.025 * BOOTSTRAP), int(0.975 * BOOTSTRAP) - 1

# Scoped arms first and in this order, so the stream matches soundness_plots.py
INTERVAL_ARMS = ["scoped_off", "scoped_left", "global_off", "global_left",
                 "blind_left", "dnf_shared"]


def loadProblems(path):
    # problem_id -> arm -> row, in file order
    problems = {}

    for row in csv.DictReader(open(path)):
        problems.setdefault(row["problem_id"], {})[row["arm"]] = row

    return list(problems.values())


def armIntervals(problems, seed=0):
    # Pooled share of solvable states solved and geometric-mean node ratio,
    # each with its interval, computed as in soundness_plots.tradeoffStats
    rng = random.Random(seed)
    stats = {}

    for arm in INTERVAL_ARMS:
        per = [(int(p[arm]["solved"]), int(p[arm]["solvable"]),
                math.log(float(p[arm]["node_ratio"]))) for p in problems]

        def coverage(sample):
            return sum(s for s, _, _ in sample) / sum(t for _, t, _ in sample)

        def geoMean(sample):
            return math.exp(sum(lg for _, _, lg in sample) / len(sample))

        boot_cov, boot_gm = [], []
        for _ in range(BOOTSTRAP):
            sample = [per[rng.randrange(len(per))] for _ in per]
            boot_cov.append(coverage(sample))
            boot_gm.append(geoMean(sample))

        boot_cov.sort()
        boot_gm.sort()

        stats[arm] = {"coverage": coverage(per), "coverage_ci": (boot_cov[LO], boot_cov[HI]),
                      "ratio": geoMean(per), "ratio_ci": (boot_gm[LO], boot_gm[HI])}

    return stats


def pairedComparison(problems, mode, seed=1):
    # Scoped minus global for one protection mode, resampling problems jointly
    # so that both rules are measured on the same draw
    scoped, glob = f"scoped_{mode}", f"global_{mode}"
    rng = random.Random(seed)

    def difference(sample):
        solvable = sum(int(p[scoped]["solvable"]) for p in sample)
        return (sum(int(p[scoped]["solved"]) for p in sample)
                - sum(int(p[glob]["solved"]) for p in sample)) / solvable

    boot = sorted(difference([problems[rng.randrange(len(problems))] for _ in problems])
                  for _ in range(BOOTSTRAP))

    solvable = sum(int(p[scoped]["solvable"]) for p in problems)
    missed_scoped = solvable - sum(int(p[scoped]["solved"]) for p in problems)
    missed_global = solvable - sum(int(p[glob]["solved"]) for p in problems)

    size = math.exp(sum(math.log(int(p[scoped]["nodes"]) / int(p[glob]["nodes"]))
                        for p in problems) / len(problems))

    return {
        "difference": difference(problems),
        "difference_ci": (boot[LO], boot[HI]),
        "global_more": sum(1 for p in problems if int(p[glob]["solved"]) > int(p[scoped]["solved"])),
        "global_fewer": sum(1 for p in problems if int(p[glob]["solved"]) < int(p[scoped]["solved"])),
        "missed_ratio": missed_global / missed_scoped if missed_scoped else float("inf"),
        "size_factor": size,
        "violations": {arm: sum(int(p[arm]["violations"]) for p in problems)
                       for arm in (scoped, glob)},
    }


def checkFlat(problems):
    # Ch. 3 equivalences on flat goals: scoped unified is the DNF tree, and
    # global unified is shared-record DNF
    return {
        "scoped_is_dnf": sum(1 for p in problems
                             if p["scoped_left"]["nodes"] != p["scoped_left"]["ref_nodes"]
                             or p["scoped_left"]["solved"] != p["scoped_left"]["both"]
                             or int(p["scoped_left"]["ref_only"])),
        "global_is_shared_dnf": sum(1 for p in problems
                                    if p["global_left"]["nodes"] != p["dnf_shared"]["nodes"]
                                    or p["global_left"]["solved"] != p["dnf_shared"]["solved"]),
    }


def fmt(value, interval, percent):
    if percent:
        return f"{100 * value:.1f} [{100 * interval[0]:.1f}, {100 * interval[1]:.1f}]"
    return f"{value:.2f} [{interval[0]:.2f}, {interval[1]:.2f}]"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nested", default="pruning_nested_minimal.csv")
    parser.add_argument("--deep", default="pruning_deep_minimal.csv")
    parser.add_argument("--flat", default=None)
    args = parser.parse_args()

    shapes = {"nested": loadProblems(args.nested), "deep": loadProblems(args.deep)}
    intervals = {shape: armIntervals(problems) for shape, problems in shapes.items()}

    for shape, problems in shapes.items():
        print(f"== {shape} ({len(problems)} problems)")

        for arm in INTERVAL_ARMS:
            s = intervals[shape][arm]
            print(f"  {arm:12} solved {fmt(s['coverage'], s['coverage_ci'], True)}"
                  f"   node ratio {fmt(s['ratio'], s['ratio_ci'], False)}")

        for mode in ("off", "left"):
            c = pairedComparison(problems, mode)
            print(f"  protect {mode}: scoped - global {100 * c['difference']:+.1f} points "
                  f"[{100 * c['difference_ci'][0]:+.1f}, {100 * c['difference_ci'][1]:+.1f}], "
                  f"global solves more on {c['global_more']} and fewer on {c['global_fewer']}, "
                  f"global misses {c['missed_ratio']:.2f}x the states, "
                  f"scoped tree {c['size_factor']:.2f}x larger, violations {c['violations']}")

    print("\n== rows of tab:scope_comparison")
    for mode, label in (("off", "Off "), ("left", "Left")):
        for record in ("scoped", "global"):
            arm = f"{record}_{mode}"
            cells = []
            for shape in ("nested", "deep"):
                s = intervals[shape][arm]
                cells += [fmt(s["coverage"], s["coverage_ci"], True),
                          fmt(s["ratio"], s["ratio_ci"], False)]
            lead = label if record == "scoped" else "    "
            print(f"    {lead} & {record.capitalize()} & " + " & ".join(cells) + r" \\")
        if mode == "off":
            print(r"    \midrule")

    if args.flat:
        flat = checkFlat(loadProblems(args.flat))
        print(f"\n== flat goals: problems where scoped unified differs from DNF "
              f"{flat['scoped_is_dnf']}, where global unified differs from shared-record DNF "
              f"{flat['global_is_shared_dnf']}")


if __name__ == "__main__":
    main()
