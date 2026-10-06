import py_trees
import py_trees_ros
import rclpy

import basic_trees.algorithms as alg

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import Load, Unload, SimActionFactory, MockMoveA, MockMoveB, MockMoveC
from basic_trees.traverse import BFS, scopedBFS, scopedCheapestFirst
from basic_trees.algorithms import expand, expansionKey, goalScope, scopedPrune
from basic_trees.Goals.goal_tree import buildBaseTree
from basic_trees.Goals.goal_types import AND, OR, goalSatisfied
from basic_trees.Sim import PoseObserver, CostMapping
from basic_trees.Sim.room_mapping import findStartRoom



MOCK = True    # Use mock actions or real actions

# "off" | "left" | "symmetric". Sibling protection is seeded at GoalSequence
# boundaries, so it is inert for a goal with no multi-child GoalSequence and
# inert for any problem where no admitted action deletes a sibling's goal
# literal. Left enabled because it costs nothing in those cases and the
# filtered counter reports which case you are in.
PROTECT_MODE = "left"


def setupWorld(blackboard, init_state, pose_map):
    # Dynamic world state
    if blackboard.is_registered(key="world_state", access=py_trees.common.Access.WRITE):
        # Key already exists, need to reset it
        blackboard.unset("world_state")
    else:
        blackboard.register_key(key="world_state", access=py_trees.common.Access.WRITE)
    
    blackboard.world_state = init_state # init_state should be a set


    if blackboard.is_registered(key="latest_room_reading", access=py_trees.common.Access.WRITE):
        # Key already exists, need to reset it
        blackboard.unset("latest_room_reading")
    else:
        blackboard.register_key(key="latest_room_reading", access=py_trees.common.Access.WRITE)
    
    blackboard.latest_room_reading = findStartRoom(init_state, pose_map) # initial room should be the room literal in init_state


def getAction(action_str, action_database):
    # Converts action name as a string to action object
    # Now only used for MOCK trials, SimFactory handles real actions    
    action_map_mock = {
        "load"   : lambda: Load(action_database=action_database),
        "unload" : lambda: Unload(action_database=action_database),
        "move_A" : lambda: MockMoveA(),
        "move_B" : lambda: MockMoveB(),
        "move_C" : lambda: MockMoveC(),
    }
    
    return action_map_mock[action_str]()


def runTree(init_state, goal_state, action_database, pose_map, traverse=scopedBFS(), tick_period=0.1):
    # Create the tree with sibling protection
    alg.PROTECT_STATS["filtered"] = 0
    root = buildBaseTree(goal_state, mode=PROTECT_MODE)

    tree = py_trees_ros.trees.BehaviourTree(
        root=root,
        unicode_tree_debug=False        # Set to True if you want to see print out of tree node statusesss
    )

    # Initialise the blackboard BEFORE setting up the tree
    blackboard = py_trees.blackboard.Client(name="Init")
    setupWorld(blackboard, init_state, pose_map) # Define world literals

    # Set up the tree
    try:
        tree.setup(node_name="my_tree", timeout=15.0)
    except py_trees_ros.exceptions.TimedOutError as e:
        print("ERROR: TREE SETUP TIMED OUT\n")
        tree.shutdown()
        return False
    
    expanded_scoped = {}     # Scoped so a condition expanded in one disjunct does not remove the other's route
    curr_world_state = set(blackboard.world_state)   # For printing world state as tree running

    if not MOCK:
        PoseObserver(tree.node, blackboard, pose_map)   # Start pose observer

        room_costs = CostMapping(tree.node, pose_map)
        room_costs.measureCosts()   # Set the intital costs

        action_factory = SimActionFactory(tree.node, action_database, pose_map, room_costs)

    ever_achieved = False       # Has the goal held at least once
    holding = False             # Did the goal hold on the previous tick
    exhausted = False           # Nothing left to expand
    false_successes = 0         # Root said SUCCESS while the goal was false
    disturbances = 0            # Goal held, then stopped holding
    reported_filtered = 0       # Last protect count printed

    print(f"protect mode: {PROTECT_MODE}")


    try:
        while rclpy.ok():
            # Handle tree returning RUNNING or FAILURE
            rclpy.spin_once(tree.node, timeout_sec=tick_period)    # Need to spin for updates, and this paces the loop
            tree.tick()

            if blackboard.world_state != curr_world_state:
                # print(f"--- tick ---")
                # print(f"status: {root.status}")
                # print(f"world_state: {blackboard.world_state}")
                curr_world_state = set(blackboard.world_state)

            satisfied = goalSatisfied(goal_state, blackboard.world_state)
        
            if root.status == py_trees.common.Status.SUCCESS and not satisfied:
                false_successes += 1
                print(f"  FALSE SUCCESS #{false_successes}: root reports SUCCESS, goal does not hold")

            if satisfied and not holding:
                ever_achieved = True
                print("  GOAL ACHIEVED - still ticking, watching for disturbances")
                py_trees.display.render_dot_tree(root, name="ROS_TREE")                 # UNCOMMENT TO RENDER THE TREE
            elif holding and not satisfied:
                disturbances += 1
                print(f"  DISTURBANCE #{disturbances}: goal no longer holds, recovering")

            holding = satisfied

            
            if root.status == py_trees.common.Status.RUNNING:
                continue # Action currently running, let it finish

            if satisfied:
                continue # Goal holds, nothing to plan for, but keep ticking so a disturbance is seen

            if exhausted:
                # Already fully expanded but a later disturbance could make the existing tree work
                # So keep ticking
                continue

            
            # FAILURE, or SUCCESS on an unsatisfied goal, tree is not yet a solution, keep expanding
            next_condition = traverse.getNextCondition(root, expanded_scoped)

            if next_condition is None:
                exhausted = True
                print(f"No more conditions to expand" + (" - unsolvable" if not ever_achieved
                         else " - cannot recover from this disturbance"))
                continue

            print(f"next_condition: {next_condition.name}")

            fc = expansionKey(next_condition)   # (literals, protect): a protected condition is not interchangeable with an unprotected one

            if MOCK:
                root = expand(root, next_condition, action_database, getAction)
            else:
                root = expand(root, next_condition, action_database, action_factory)

            expanded_scoped.setdefault(fc, set()).add(goalScope(next_condition))
            scopedPrune(root, expanded_scoped)  # Remove sequence structures already expanded in this same scope

            tree.root = root


            # Report protect activity only when it changes. Nonzero means this
            # problem genuinely interferes.
            filtered = alg.PROTECT_STATS["filtered"]
            if filtered > reported_filtered:
                print(f"  protect filtered {filtered} action(s) so far - this problem DOES interfere")
                reported_filtered = filtered

    except KeyboardInterrupt:
        print("\n  interrupted")

    finally:
        print(f"\n  goal achieved    : {ever_achieved}")
        print(f"  disturbances     : {disturbances}")
        print(f"  false successes  : {false_successes}")
        print(f"  protect mode     : {PROTECT_MODE}")
        print(f"  actions filtered : {alg.PROTECT_STATS['filtered']}")
        tree.shutdown() # Delete tree

    return ever_achieved


def main(args=None):
    rclpy.init(args=args)

    # Set enviroment
    # init_state = {"empty", "at_B"}
    # goal_state = OR(AND("at_A", "full"), AND("at_C", "full"))

    # # Cost in action_database is only for MOCK but not implemented for MOCK yet
    # action_database = {
    #         "load"     : {"pre" : ["empty"],            "add" : ["full"],                           "del" : ["empty"],          "cost" : 2.0},
    #         "unload"   : {"pre" : ["full", "at_B"],     "add" : ["empty", "package_delivered"],     "del" : ["full"],           "cost" : 1.0},
    #         "move_A"   : {"pre" : [],                   "add" : ["at_A"],                           "del" : ["at_B", "at_C"],   "cost" : 1.0},
    #         "move_B"   : {"pre" : [],                   "add" : ["at_B"],                           "del" : ["at_A", "at_C"],   "cost" : 2.0},
    #         "move_C"   : {"pre" : [],                   "add" : ["at_C"],                           "del" : ["at_A", "at_B"],   "cost" : 3.0},
    #         } 

    pose_map = {
        "A": {"goal": (0.0, 4.5, 1.0),  "bounds": ((-3.25, 3.25), (0.75, 8.25)),    "literal": "at_A"}, # Red object
        "B": {"goal": (0.0, -4.5, 1.0), "bounds": ((-3.25, 3.25), (-8.25, -0.75)),  "literal": "at_B"}, # Big Room
        "C": {"goal": (9.0, 0.0, 1.0),  "bounds": ((4.75, 13.25), (-8.25, 8.25)),   "literal": "at_C"},
    }

    init_state = {"at_start"}
    goal_state = OR(AND("has_key", "at_A"), AND("has_key", "at_C"))

    action_database = {
        "get_key":  {"pre": ["at_start"], "add": ["has_key"], "del": [],        "cost": 1.0},
        "go_A":     {"pre": [],           "add": ["at_A"],    "del": ["at_C", "at_start"], "cost": 5.0},
        "go_C":     {"pre": [],           "add": ["at_C"],    "del": ["at_A", "at_start"], "cost": 3.0},
    }


    try:
        runTree(init_state, goal_state, action_database, pose_map)
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()