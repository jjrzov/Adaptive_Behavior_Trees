#include <string>
#include <memory>

#include "behaviortree_cpp/action_node.h"
#include "behaviortree_cpp/bt_factory.h"
#include "behaviortree_cpp/utils/shared_library.h"

#include "ament_index_cpp/get_package_share_directory.hpp"

#include "rclcpp/rclcpp.hpp"

using namespace bump_and_go;

int main(int argc, char *argv[]) 
{
    rclcpp::init(argc, argv);

    auto node = rclcpp::Node::make_shared("patrolling_node");

    BT::BehaviorTreeFactory factory;
    BT::SharedLibrary loader;

    factory.registerFromPlugin(loader.getOSName("bg_forward_node"));
    // factory.registerFromPlugin(loader.getOSName("br2_back_bt_node"));
    // factory.registerFromPlugin(loader.getOSName("br2_turn_bt_node"));
    // factory.registerFromPlugin(loader.getOSName("br2_is_obstacle_bt_node"));

    std::string pkgpath = ament_index_cpp::get_package_share_directory("bump_and_go");
    std::string xml_file = pkgpath + "/behavior_tree_xml/bumpgo.xml";

    // auto blackboard = BT::Blackboard::create();
    // blackboard->set("node", node);

    BT::NodeConfig config;
    config.blackboard = BT::Blackboard::create();

    // Create Tree
    auto root_seq = std::make_shared<BT::SequenceNode>("sequence", config);
    auto action = std::make_shared<Forward>("forward", config);

    root_seq->addChild(action.get());

    // You'd then need to manually tick the root
    root_seq->executeTick();

    rclcpp::Rate rate(10);

    bool finish = false;
    while (!finish && rclcpp::ok()) {
        finish = root_seq.executeTick() != BT::NodeStatus::RUNNING;

        rclcpp::spin_some(node);
        rate.sleep();
    }

    rclcpp::shutdown();
    return 0;
}