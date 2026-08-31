import csv
import basic_trees.algorithms as alg

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution
from basic_trees.Goals.goal_tree import runTree, runDNF
from basic_trees.Testing.OR_Testing.histogram import getDisjunctSets
from basic_trees.Goals.goal_types import OR, AND
from basic_trees.Testing.test_tree import getNodeCount
from basic_trees.traverse import *

TARGET_RUNS = 2000

FIELDS = ["problem_id", "arm", "dist1", "dist2", "min", "max", "spread",
          "solved", "node_count", "expansions", "disjunct_reached", "picked_cheapest"]


def whichDisjunct(final_state, d1, d2):
    # Retuns which disjunct was choosen by the tree
    s = set(final_state)
    in1 = set(d1).issubset(s)
    in2 = set(d2).issubset(s)

    if in1 and in2:
        return "both"
    if in1:
        return "d1"
    if in2:
        return "d2"
    return "neither"


def runCase(case, traversals, out_path):
    alg.SUBSET_PRUNE = False
    alg.DEDUP_C_ATTR = False

    solved_count = 0

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for p_index in range(TARGET_RUNS):

            # Generate initial state, action database, and state pool as base paper does
            all_literals = generateLiterals(case["literals"])
            states_db, action_db = generateSolution(all_literals, case["distance"], case["iterations"])

            # Generate the disjuncts
            sample = getDisjunctSets(states_db, action_db)
            if sample is None:
                continue
            d1, d2, dist1, dist2 = sample   # the literal sets, not the distances

            for name, algo in traversals:
                goal = OR(AND(*d1), AND(*d2))

                if name == "DNF":
                    root, exp, last_state = runDNF(states_db[0].copy(), [d1, d2], action_db, traverse=algo)
                else:
                    root, exp, last_state = runTree(states_db[0].copy(), goal, action_db, traverse=algo)

                solved = root is not False  # Recored if solved problem
                reached = whichDisjunct(last_state, d1, d2) if (solved and name != "DNF") else ""
                cheaper = "d1" if dist1 <= dist2 else "d2"

                if name == "DNF":
                    writer.writerow({
                        "problem_id": p_index,
                        "arm": name,
                        "dist1": dist1,
                        "dist2": dist2,
                        "min": min(dist1, dist2),
                        "max": max(dist1, dist2),
                        "spread": abs(dist1 - dist2),
                        "solved": solved,
                        "node_count": getNodeCount(root) if solved else "",
                        "expansions": exp,
                    })
                else:
                    writer.writerow({
                        "problem_id": p_index,
                        "arm": name,
                        "dist1": dist1,
                        "dist2": dist2,
                        "min": min(dist1, dist2),
                        "max": max(dist1, dist2),
                        "spread": abs(dist1 - dist2),
                        "solved": solved,
                        "node_count": getNodeCount(root) if solved else "",
                        "expansions": exp,
                        "disjunct_reached": reached,
                        "picked_cheapest": reached == cheaper,
                    })

            solved_count += 1
            if solved_count % 500 == 0:
                print(f"  Case {case['case']}: {solved_count} problems")


def main():
    test_case = {"case": 1, "literals": 100, "distance": 100, "iterations": 10}
    print(f"literals = {test_case['literals']}, distance = {test_case['distance']}, iterations = {test_case['iterations']}")

    # All traversals for finding the next condition to expand
    traversals = [("BFS", BFS()), ("DFS", DFS()), ("CheapestFirst", CheapestFirst()), ("DNF", BFS())]

    runCase(test_case, traversals, "or_sweep.csv")


if __name__ == '__main__':
    main()