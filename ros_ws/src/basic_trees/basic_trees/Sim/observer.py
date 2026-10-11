import py_trees
from geometry_msgs.msg import PoseWithCovarianceStamped

class PoseObserver():
    '''
    Writes the room literal of the robot's AMCL pose to the world state.

    Each room is an axis-aligned rectangle. A pose inside a rectangle replaces
    whatever room literal was held with that room's literal. A pose outside
    every rectangle (a doorway or the gap between rooms) changes nothing, so the
    last room literal stays in place until the robot is seen inside another
    room. That hysteresis keeps exactly one room literal in the world state
    once the first pose has been classified.
    '''

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
        for key, room in self.pose_map.items():
            (x_min, x_max), (y_min, y_max) = room["bounds"]
            if x_min <= x <= x_max and y_min <= y <= y_max:
                return key
        return None


    def observer_callback(self, msg):
        curr_key = self._classify(msg.pose.pose.position.x, msg.pose.pose.position.y)

        # In the gap between rooms: keep the last reading (hysteresis)
        if curr_key is None:
            return

        # Inside a room: it becomes the only room literal held
        for room in self.pose_map.values():
            self.blackboard.world_state.discard(room["literal"])

        self.blackboard.latest_room_reading = curr_key
        self.blackboard.world_state.add(self.pose_map[curr_key]["literal"])

