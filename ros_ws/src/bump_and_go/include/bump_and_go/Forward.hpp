#ifndef BUMP_AND_GO__FORWARD_HPP_
#define BUMP_AND_GO__FORWARD_HPP_

#include <string>

#include "behaviortree_cpp/behavior_tree.h"
#include "behaviortree_cpp/bt_factory.h"

#include "geometry_msgs/msg/twist.hpp"
#include "rclcpp/rclcpp.hpp"

namespace bump_and_go 
{

class Forward : public BT::ActionNodeBase
{
public:
    explicit Forward(
        const std::string & xml_tag_name,
        const BT::NodeConfiguration & conf);

    void halt() {}
    BT::NodeStatus tick();

    static BT::PortsList providedPorts()
    {
    return BT::PortsList({});
    }

private:
    rclcpp::Node::SharedPtr node_;
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr vel_pub_;
};

} // namespace bump_and_go

#endif // BUMP_AND_GO__FORWARD_HPP_