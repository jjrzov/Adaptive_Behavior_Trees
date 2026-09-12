# This code replicates the BTExpansion Testing Setup and Procedure

import random
import math
import heapq


# Test Setup Parameters
NUM_OF_LITERALS = 10   # Amount of literals 2^N possible states
DISTANCE = 10    # Amount of states from start to goal
ITERATIONS = 10  # Amount of times to branch from generated path
COST_MIN = 1.0  # Min bound for cost of an action
COST_MAX = 1000.0 # Max bound for cost of an action
MAX_HOP_GAP = 2

def generateAction(literals, state):
    # Generate a random action using the world state and all literals
    pre, add, dels = set(), set(), set()

    for literal in literals:
        if literal in state:
            if random.random() > 0.5:
                pre.add(literal)
            if random.random() > 0.5:
                dels.add(literal)
        else:
            # Literals not in state
            if random.random() > 0.5:
                add.add(literal)
            else:
                if random.random() > 0.5:
                    dels.add(literal)

    # cost = random.uniform(COST_MIN, COST_MAX)   # Randomly sample the cost with a UNIFORM distribution
    cost = math.exp(random.uniform(math.log(COST_MIN), math.log(COST_MAX))) # Log Uniform distribution

    return {"pre": pre, "add": add, "del": dels, "cost": cost}


def generateLiterals(num_literals=NUM_OF_LITERALS):
    # Create list of all possible literals
    return [f"literal_{i}" for i in range(num_literals)]


def generateSolution(all_literals, distance=DISTANCE, iterations=ITERATIONS):
    # Step 1: Generate Initial State
    curr_state = set()

    for literal in all_literals:
        if random.random() > 0.5:
            curr_state.add(literal)  # Select each literal w/ 50% chance

    # Store Tree Creation Info
    states_database = []    # Store path states
    action_database = {}    # Store possible actions

    for i in range(distance):
        # Iteratively generate a path

        # Step 2: Generate a Random Action
        rand_action = generateAction(all_literals, curr_state)

        # Step 3: Calculate Successor State
        next_state = curr_state.union(rand_action["add"]) - rand_action["del"]
        
        # Store info
        action_database[f"action_{i}"] = rand_action # Store generated action in database
        states_database.append(curr_state)
        curr_state = next_state     # Iterate states

    states_database.append(curr_state)  # Append final state

    # Step 4: Randomly generate an action from a random existing state
    states_pool = list(states_database)

    for i in range(iterations):
        rand_state = random.choice(states_pool)
        rand_action_branch = generateAction(all_literals, rand_state)
        action_database[f"action_branch_{i}"] = rand_action_branch # Store generated action in database
        states_pool.append(rand_state.union(rand_action_branch["add"]) - rand_action_branch["del"]) # Calculate branching successor state

    return states_database, action_database


def printTestSet(all_literals, states_database, action_database):
    print("=" * 50)
    print("TEST SET")
    print("=" * 50)
    
    print(f"\nLITERALS ({len(all_literals)}):")
    print(f"  {all_literals}")
    
    print(f"\nSTATES (distance = {len(states_database) - 1}):")
    for i, state in enumerate(states_database):
        label = "  [init]" if i == 0 else ("[goal]" if i == len(states_database) - 1 else f"  [s{i}]  ")
        print(f"  {label}: {sorted(state)}")
    
    print(f"\nACTIONS ({len(action_database)}):")
    for action, effects in action_database.items():
        print(f"  {action}:")
        print(f"    pre: {sorted(effects['pre'])}")
        print(f"    add: {sorted(effects['add'])}")
        print(f"    del: {sorted(effects['del'])}")
    
    print("=" * 50)

    
def getRandomSubset(state):
    subset = set()

    for literal in state:
        if random.random() > 0.25:
            subset.add(literal)

    return subset


def unweightedDistToSubset(states_database, action_database, disjunct):
    # Imnplements BFS to get node count from the root to the disjunct
    depth = 0

    q = [(states_database[0], depth)]  # Initialize queue
    visited = {frozenset(states_database[0])}
    states_pool = {frozenset(s) for s in states_database}

    while (len(q) != 0):
        # Keep searching until empty
        state, depth = q.pop(0)
        if disjunct.issubset(state):
            return depth

        for _, ops in action_database.items():
            if ops["pre"].issubset(state):
                # action is possible because the state has its preconditions
                next_state = frozenset(state.union(ops["add"]) - ops["del"])   # Calulate possible next state

                if (next_state not in visited) and (next_state in states_pool):
                    # Possible next state hasn't been explored and is in the state pool
                    visited.add(next_state)
                    q.append((next_state, depth + 1))

    return math.inf # No valid state found


def weightedDistToSubset(states_database, action_database, disjunct):
    # Implements Dijkstra to get cost from the root to the disjunct
    counter = 0
    states_pool = {frozenset(s) for s in states_database}
    start = frozenset(states_database[0])

    best = {start: 0.0}
    pq = [(0.0, counter, start)]    # Priority Q holding (cost, node)
    stale = set()   # Keep track of nodes incase of stale entries

    while pq:
        cost, _, state = heapq.heappop(pq)

        if state in stale:
            continue    # Skip if already visited

        stale.add(state)

        if disjunct.issubset(state):
            return cost

        for _, ops in action_database.items():
            if ops["pre"].issubset(state):
                # action is possible because the state has its preconditions
                next_state = frozenset(state.union(ops["add"]) - ops["del"])   # Calulate possible next state

                if next_state not in states_pool:
                    continue    # Created a state not in the pre-generated states pool, skip in

                new_cost = cost + ops["cost"]
                if new_cost < best.get(next_state, math.inf):
                    best[next_state] = new_cost     # Shorter path found
                    counter += 1    # Increment counter for tie breaking
                    heapq.heappush(pq, (new_cost, counter, next_state))

    return math.inf


def getDisjunctSets(states_database, action_database):
    # Pick 2 random and distinct states
    max_attempts = 50

    for _ in range(max_attempts):
        s1 = set(random.choice(states_database))
        s2 = set(random.choice(states_database))

        if (s2 == s1):
            continue

        # Get a random subset of both
        d1 = getRandomSubset(s1)                        
        d2 = getRandomSubset(s2)

        if (d1.issubset(states_database[0]) or d2.issubset(states_database[0]) 
                or (d1.issubset(d2) or d2.issubset(d1))):
            continue

        # Caluclate distance from a state containing the disjuct set and the root
        dist1 = unweightedDistToSubset(states_database, action_database, d1)
        dist2 = unweightedDistToSubset(states_database, action_database, d2)

        return d1, d2, dist1, dist2

    return None


def getDisjunctSetsWithCosts(states_database, action_database):
    # Pick 2 random and distinct states
    max_attempts = 50

    for _ in range(max_attempts):
        s1 = set(random.choice(states_database))
        s2 = set(random.choice(states_database))

        if (s2 == s1):
            continue

        # Get a random subset of both
        d1 = getRandomSubset(s1)                        
        d2 = getRandomSubset(s2)

        if (d1.issubset(states_database[0]) or d2.issubset(states_database[0]) 
                or (d1.issubset(d2) or d2.issubset(d1))):
            continue

        hops1 = unweightedDistToSubset(states_database, action_database, d1)
        hops2 = unweightedDistToSubset(states_database, action_database, d2)

        if abs(hops1 - hops2) > MAX_HOP_GAP:
            continue

        # Caluclate distance from a state containing the disjuct set and the root
        dist1 = weightedDistToSubset(states_database, action_database, d1)
        dist2 = weightedDistToSubset(states_database, action_database, d2)

        return d1, d2, dist1, dist2

    return None


def main():
    all_literals = generateLiterals()
    states_database, action_database = generateSolution(all_literals)

    printTestSet(all_literals, states_database, action_database)

if __name__ == '__main__':
    main()