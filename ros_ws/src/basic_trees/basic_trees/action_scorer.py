

action_time_database = {
        "load_1"   : 5,
        "unload_1" : 1,
        "move_A"   : 2,
        "move_B"   : 3,
        "move_C"   : 4,
        } 

class ActionScorer:
    def sort(self, goal_condition, valid_actions):
        pass

class ConditionCompletionScorer(ActionScorer):
    def __init__(self, action_database):
        self.action_database = action_database

    def sort(self, goal_condition, valid_actions):
        return sorted(valid_actions, 
                    key=lambda x: len(goal_condition.intersection(set(self.action_database[x[0]]["add"]))), 
                    reverse=True)

class TimeScorer(ActionScorer):
    def sort(self, goal_condition, valid_actions):
        return sorted(valid_actions,
                    key=lambda x: action_time_database[x[0]],
                    reverse=False)