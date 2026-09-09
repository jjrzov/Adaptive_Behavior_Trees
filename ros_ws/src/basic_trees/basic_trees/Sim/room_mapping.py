import rclpy
import math

from rclpy.action import ActionClient
from nav2_msgs.action import ComputePathToPose
from action_msgs.msg import GoalStatus

from itertools import combinations
from math import hypot


def findStartRoom(init_state, pose_map):
    for key, room in pose_map.items():
        if room["literal"] in init_state:
            return key
    return None


class CostMapping():
    def __init__(self, node, pose_map):
        self.node = node
        self.pose_map = pose_map

        self.nav_client = ActionClient(
            node, 
            ComputePathToPose, 
            'compute_path_to_pose'
        )

        self.edges = {} # Dict of directed edges(cost) for going between rooms


    def _path_length(self, path):
        # Compute the length of the path by adding euclidean distance between sequential poses
        poses = path.poses
        total = 0.0

        if len(poses) < 2:
            # No path found
            return math.inf


        for i in range(1, len(poses)):
            p0 = poses[i-1].pose.position
            p1 = poses[i].pose.position
            total += hypot(p1.x - p0.x, p1.y - p0.y)
        
        return total


    def _measure(self, start, end):
        # Measure the total length of the path from start to end
        msg = ComputePathToPose.Goal()

        msg.use_start = True # Use start pose instead of robot pose as start

        msg.start.header.frame_id = 'map'
        msg.start.pose.position.x = start[0]
        msg.start.pose.position.y = start[1]
        msg.start.pose.orientation.w = start[2]

        msg.goal.header.frame_id = 'map'
        msg.goal.pose.position.x = end[0]
        msg.goal.pose.position.y = end[1]
        msg.goal.pose.orientation.w = end[2]


        future = self.nav_client.send_goal_async(msg)   # Send the msg to the ActionClient
        # Block until completed because its async
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=15.0)
        if not future.done():
            raise RuntimeError("FAILED TO SEND PATH FOR COST")

        client_goal_handle = future.result()
        if client_goal_handle.accepted:
            future = client_goal_handle.get_result_async()  # Receive the msg from the ActionClient

            # Block until completed because its async
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=15.0)
            if not future.done():
                raise RuntimeError("FAILED TO RECEIVE PATH FOR COST")

            # Make sure there is a result to be read first
            wrapper = future.result()
            if wrapper.status != GoalStatus.STATUS_SUCCEEDED:
                return math.inf
            
            return self._path_length(wrapper.result.path)

        return math.inf


    def measureCosts(self):
        # Find the cost of moving between rooms

        # Wait for Nav2 Action client to setup
        if not self.nav_client.wait_for_server(timeout_sec=15.0):
            raise RuntimeError("FAILED TO START NAV2 ACTION CLIENT")

        # Loop through all combinations of rooms        
        for a, b in combinations(self.pose_map.keys(), 2):  
            # Do permutations instead of combinations of a directed graph is desired
            
            length = self._measure(self.pose_map[a]["goal"], self.pose_map[b]["goal"])
            self.edges[(a, b)] = length
            self.edges[(b, a)] = length      # symmetric


    def getRoomCost(self, current, dest):
        # Return the cost from the current room to the destination room
        if current == dest:
            return 0
        
        if current not in self.pose_map or dest not in self.pose_map:
           raise KeyError(f"Unknown room: {current} -> {dest}")

        return self.edges[(current, dest)]