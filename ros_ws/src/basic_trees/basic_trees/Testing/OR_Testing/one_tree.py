import csv
import basic_trees.algorithms as alg

from basic_trees.Testing.setup_tests import generateLiterals, generateSolution
from basic_trees.Goals.goal_tree import runTree
from basic_trees.Testing.OR_Testing.histogram import getDisjunctSets
from basic_trees.Goals.goal_types import OR, AND
from basic_trees.Testing.test_tree import getNodeCount
from basic_trees.traverse import *
from basic_trees.Testing.OR_Testing.or_driver import whichDisjunct


TARGET_RUNS = 1


def runCase(case, traversals):
    alg.SUBSET_PRUNE = False
    alg.DEDUP_C_ATTR = False


    for _ in range(TARGET_RUNS):

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
            root, exp, last_state = runTree(states_db[0].copy(), goal, action_db, traverse=algo)

            solved = root is not False  # Recored if solved problem

            reached = whichDisjunct(last_state, d1, d2) if solved else ""
            cheaper = "d1" if dist1 <= dist2 else "d2"

            print(f"{name}")
            print(f"Dist1: {dist1}\t Dist2: {dist2}\t Min: {min(dist1, dist2)}\t Max: {max(dist1, dist2)}")
            print(f"Reached: {reached}\nCheaper: {cheaper}\nPicked Cheapest: {reached == cheaper}\n")


def main():
    test_case = {"case": 1, "literals": 100, "distance": 100, "iterations": 10}
    print(f"literals = {test_case['literals']}, distance = {test_case['distance']}, iterations = {test_case['iterations']}")

    # All traversals for finding the next condition to expand
    traversals = [("BFS", BFS()), ("DFS", DFS()), ("CheapestFirst", CheapestFirst())]

    runCase(test_case, traversals)


if __name__ == '__main__':
    main()