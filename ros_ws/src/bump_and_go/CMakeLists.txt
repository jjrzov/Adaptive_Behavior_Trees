cmake_minimum_required(VERSION 3.8)
project(bump_and_go)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(behaviortree_cpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(ament_index_cpp REQUIRED)


set(dependencies
    rclcpp::rclcpp
    behaviortree_cpp::behaviortree_cpp
    ament_index_cpp::ament_index_cpp
    ${sensor_msgs_TARGETS}
    ${geometry_msgs_TARGETS}
)

add_library(bg_forward_node SHARED src/ControlNodes/Forward.cpp)

list(APPEND plugin_libs
  bg_forward_node
)

foreach(bt_plugin ${plugin_libs})
  target_include_directories(${bt_plugin} PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
  )
  target_link_libraries(${bt_plugin} ${dependencies})
  target_compile_definitions(${bt_plugin} PRIVATE BT_PLUGIN_EXPORT)
endforeach()

add_executable(bumpgo src/bump_and_go.cpp)
target_link_libraries(bumpgo ${dependencies})

install(TARGETS
  ${plugin_libs}
  bumpgo
  DESTINATION lib/${PROJECT_NAME}
)
  

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
