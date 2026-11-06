'''
Video version of ros_tree.py: the same simulation run, plus

  - a TreeRecorder that saves the tree every time its shape or a node's status
    changes, into tree_frames_<PROTECT_MODE>/, for a video of the tree beside a
    screen recording of the robot
  - a pause of VIDEO_HOLD seconds before and after each expansion, so the
    changes can be followed. The robot is stopped during every pause.

Use ros_tree.py for timing runs. This file logs to sim_timing_video.csv, whose
times include the pauses.

    ros2 run basic_trees video
    python3 render_tree_video.py tree_frames_left --out tree_left.mp4
'''
import time

import py_trees
import py_trees_ros
import rclpy

import basic_trees.algorithms as alg

from basic_trees.Conditions.condition import Condition
from basic_trees.Actions import Load, Unload, SimActionFactory, MockMoveA, MockMoveB, MockMoveC, TestAction
from basic_trees.traverse import BFS, scopedBFS, scopedCheapestFirst
from basic_trees.algorithms import expand, expansionKey, goalScope, scopedPrune
from basic_trees.Goals.goal_tree import buildBaseTree
from basic_trees.Goals.goal_types import AND, OR, goalSatisfied
from basic_trees.Sim import PoseObserver, CostMapping
from basic_trees.Sim.room_mapping import findStartRoom
from basic_trees.Sim.tick_logger import TickLogger
from basic_trees.Sim.tree_recorder import TreeRecorder



MOCK = False    # Use mock actions or real actions

# "off" | "left" | "symmetric". Sibling protection is seeded at GoalSequence
# boundaries, so it is inert for a goal with no multi-child GoalSequence and
# inert for any problem where no admitted action deletes a sibling's goal
# literal. Left enabled because it costs nothing in those cases and the
# filtered counter reports which case you are in.
PROTECT_MODE = "off"

# Seconds to pause before and after each expansion, so a recording of the tree
# can be followed. Expansion only happens when no action is running, so the robot
# is stopped during the pause. Set to 0 for timing runs, since sim_timing.csv
# would otherwise include the pauses.
VIDEO_HOLD = 1.5


def holdFor(tree, seconds, tick_period):
    # Wait without ticking, but keep ROS callbacks (the pose observer) flowing
    end = time.monotonic() + seconds
    while rclpy.ok() and time.monotonic() < end:
        rclpy.spin_once(tree.node, timeout_sec=tick_period)


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
        "scan"     : lambda: TestAction(name="scan", action_database=action_database),
        "load"     : lambda: TestAction(name="load", action_database=action_database),
        "unload_A" : lambda: TestAction(name="unload_A", action_database=action_database),
        "unload_C" : lambda: TestAction(name="unload_C", action_database=action_database),
        "move_A"   : lambda: MockMoveA(),
        "move_B"   : lambda: MockMoveB(),
        "move_C"   : lambda: MockMoveC(),
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
    
    logger = TickLogger(tree.node, out_path="sim_timing_video.csv")   # Kept apart from ros_tree.py's timing log

    # Record the tree whenever it changes, for a video next to the robot footage.
    # The snapshot visitor reports which nodes each tick actually visited.
    snapshot = py_trees.visitors.SnapshotVisitor()
    tree.add_visitor(snapshot)
    recorder = TreeRecorder(out_dir=f"tree_frames_{PROTECT_MODE}")

    expanded_scoped = {}     # Scoped so a condition expanded in one disjunct does not remove the other's route
    curr_world_state = set(blackboard.world_state)   # For printing world state as tree running

    if not MOCK:
        PoseObserver(tree.node, blackboard, pose_map)   # Start pose observer

        room_costs = CostMapping(tree.node, pose_map)

        action_factory = SimActionFactory(tree.node, action_database, pose_map, room_costs)

    ever_achieved = False       # Has the goal held at least once
    holding = False             # Did the goal hold on the previous tick
    exhausted = False           # Nothing left to expand
    false_successes = 0         # Root said SUCCESS while the goal was false
    disturbances = 0            # Goal held, then stopped holding
    reported_filtered = 0       # Last protect count printed

    print(f"protect mode: {PROTECT_MODE}")

    # Show the tree before anything has ticked. An empty visited map makes every
    # node INVALID, so the whole tree draws white.
    recorder.after_tick(root, {})
    holdFor(tree, VIDEO_HOLD, tick_period)     # Let the untouched tree show before the first tick

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
            logger.after_tick(root, blackboard.world_state, satisfied)
            recorder.after_tick(root, snapshot.visited)
        
            if root.status == py_trees.common.Status.SUCCESS and not satisfied:
                false_successes += 1
                print(f"  FALSE SUCCESS #{false_successes}: root reports SUCCESS, goal does not hold")

            if satisfied and not holding:
                ever_achieved = True
                print("  GOAL ACHIEVED - still ticking, watching for disturbances")
                py_trees.display.render_dot_tree(root, name="ROS_TREE_C_DOOR")                 # UNCOMMENT TO RENDER THE TREE
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
            holdFor(tree, VIDEO_HOLD, tick_period)     # Let the failed tick show before the tree grows
            logger.expansion(next_condition)

            fc = expansionKey(next_condition)   # (literals, protect): a protected condition is not interchangeable with an unprotected one

            if MOCK:
                root = expand(root, next_condition, action_database, getAction)
            else:
                root = expand(root, next_condition, action_database, action_factory)

            expanded_scoped.setdefault(fc, set()).add(goalScope(next_condition))
            scopedPrune(root, expanded_scoped)  # Remove sequence structures already expanded in this same scope

            tree.root = root
            recorder.after_tick(root, snapshot.visited)    # Show the tree as soon as it grows
            holdFor(tree, VIDEO_HOLD, tick_period)         # Let the new subtree show before it is ticked


            # Report protect activity only when it changes. Nonzero means this problem genuinely interferes.
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
        logger.close()
        recorder.close()
        tree.shutdown() # Delete tree

    return ever_achieved


def main(args=None):
    rclpy.init(args=args)

    pose_map = {
        "A": {"goal": (0.0,  4.5, 1.0), "bounds": ((-3.25, 3.25), (0.75, 8.25)),   "literal": "at_A"},
        "B": {"goal": (9.0, -3.0, 1.0), "bounds": ((4.75, 13.25), (-8.25, 8.25)),  "literal": "at_B"},  # hub
        "C": {"goal": (0.0, -4.5, 1.0), "bounds": ((-3.25, 3.25), (-8.25, -0.75)), "literal": "at_C"},
    }

    # Warehouse task: scan the package, then leave it in bin A or bin C.
    # Room B is the hub where the robot starts and the package is picked up.
    init_state = {"at_B", "empty", "door_C_closed"}
    goal_state = AND("door_C_closed", "scanned", OR("box_at_A", "box_at_C"))

    # Move costs are measured by CostMapping at startup. The costs listed here
    # are used by scan, load and unload, which have no path to measure.
    action_database = {
        "scan"          : {"pre": ["at_B"],          "add": ["scanned"],              "del": [],                "cost": 2.0},
        "load"          : {"pre": ["empty", "at_B"], "add": ["full"],                 "del": ["empty"],         "cost": 2.0},
        "unload_A"      : {"pre": ["full", "at_A"],  "add": ["box_at_A", "empty"],    "del": ["full"],          "cost": 2.0},
        "unload_C"      : {"pre": ["full", "at_C"],  "add": ["box_at_C", "empty"],    "del": ["full"],          "cost": 2.0},
        "move_A"        : {"pre": [],                "add": ["at_A"],                 "del": ["at_B", "at_C"],  "cost": 1.0},
        "move_B"        : {"pre": [],                "add": ["at_B"],                 "del": ["at_A", "at_C"],  "cost": 1.0},
        "move_C"        : {"pre": ["door_C_open"],   "add": ["at_C"],                 "del": ["at_A", "at_B"],  "cost": 1.0},
        "open_door_C"   : {"pre": ["at_B"],          "add": ["door_C_open"],          "del": ["door_C_closed"], "cost": 1.0},
    }

    try:
        runTree(init_state, goal_state, action_database, pose_map,
                traverse=scopedBFS())
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()