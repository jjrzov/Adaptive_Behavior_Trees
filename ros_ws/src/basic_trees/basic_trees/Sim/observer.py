from geometry_msgs.msg import PoseWithCovarianceStamped

class PoseObserver():
    def __init__(self, node, blackboard, pose_map):
        self.node = node
        self.blackboard = blackboard
        self.pose_map = pose_map

        # Create a subscription attaced to Tree's node to avoid making a separate node
        self.subscription = self.node.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.observer_callback,
            10
        )

    def _classify(self, x, y):
        # Classifies pose into respective room
        for room in self.pose_map.values():
            (x_min, x_max), (y_min, y_max) = room["bounds"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                return room["literal"]
        return None

    def observer_callback(self, msg):
        pose_x = msg.pose.pose.position.x
        pose_y = msg.pose.pose.position.y


        curr_literal = self._classify(pose_x, pose_y)
        
        for room in self.pose_map.values():
            self.blackboard.world_state.discard(room["literal"])

        if curr_literal != None:
            # Not in hystersis buffer area
            self.blackboard.world_state.add(curr_literal)

