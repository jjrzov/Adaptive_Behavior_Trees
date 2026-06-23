# This code replicates the BTExpansion Testing Setup and Procedure

import random

# Test Setup Parameters
NUM_OF_LITERALS = 5   # Amount of literals 2^N possible states
DISTANCE = 10    # Amount of states from start to goal
ITERATIONS = 10  # Amount of times to branch from generated path


def generateAction(literals, state):
    # Generate a random action using the world state and all literals
    pre, add, dels = set(), set(), set()

    for literal in literals:
        if literal in state:
            if random.random() > 0.5:
                pre.add(literal)
            else:
                if random.random() > 0.5:
                    dels.add(literal)
        else:
            # Literals not in state
            if random.random() > 0.5:
                add.add(literal)
            else:
                if random.random() > 0.5:
                    dels.add(literal)

    return {"pre": pre, "add": add, "del": dels}

def generateLiterals():
    # Create list of all possible literals
    return [f"literal_{i}" for i in range(NUM_OF_LITERALS)]

def generateSolution(all_literals):
    # Step 1: Generate Initial State
    curr_state = set()

    for literal in all_literals:
        if random.random() > 0.5:
            curr_state.add(literal)  # Select each literal w/ 50% chance

    # Store Tree Creation Info
    states_database = []    # Store path states
    action_database = {}    # Store possible actions

    for i in range(DISTANCE):
        # Iteratively generate a path

        # Step 2: Generate a Random Action
        rand_action = generateAction(all_literals, curr_state)

        # Step 3: Calculate Successor State
        next_state = curr_state.union(rand_action["add"] - rand_action["del"])
        
        # Store info
        action_database[f"action_{i}"] = rand_action # Store generated action in database
        states_database.append(curr_state)
        curr_state = next_state     # Iterate states

    # Step 4: Randomly generate an action from a random existing state
    for i in range(ITERATIONS):
        rand_state = random.choice(states_database)
        rand_action_branch = generateAction(all_literals, rand_state)
        action_database[f"action_branch_{i}"] = rand_action_branch # Store generated action in database

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


def main():
    all_literals = generateLiterals()
    states_database, action_database = generateSolution(all_literals)

    printTestSet(all_literals, states_database, action_database)

if __name__ == '__main__':
    main()