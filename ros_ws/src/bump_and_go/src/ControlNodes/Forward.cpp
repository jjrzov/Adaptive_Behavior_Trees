#include <string>
#include <iostream>

#include "bump_and_go/Forward.hpp"

#include "behaviortree_cpp/behavior_tree.h"

#include "geometry_msgs/msg/twist.hpp"
#include "rclcpp/rclcpp.hpp"

namespace bump_and_go
{

using namespace std::chrono_literals;

Forward::Forward(
    const std::string & xml_tag_name,
    const BT::NodeConfiguration & conf)
: BT::ActionNodeBase(xml_tag_name, conf)
{
    [[maybe_unused]] bool success = config().blackboard->get("node", node_);

    vel_pub_ = node_->create_publisher<geometry_msgs::msg::Twist>("/output_vel", 100);
}

BT::NodeStatus
Forward::tick()
{
    geometry_msgs::msg::Twist vel_msgs;
    vel_msgs.linear.x = 0.3;
    vel_pub_->publish(vel_msgs);

    return BT::NodeStatus::RUNNING;
}

}  // namespace bump_and_go

#include "behaviortree_cpp/bt_factory.h"
BT_REGISTER_NODES(factory)
{
    factory.registerNodeType<bump_and_go::Forward>("Forward");
}