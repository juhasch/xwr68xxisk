cmake_minimum_required(VERSION 3.10)
project(xwr68xxisk)

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Set Python path to help CMake find the correct Python installation
set(Python3_EXECUTABLE "/Users/juhasch/miniforge3/envs/ros2_kilted/bin/python3")
set(Python3_INCLUDE_DIR "/Users/juhasch/miniforge3/envs/ros2_kilted/include/python3.12")
set(Python3_NumPy_INCLUDE_DIRS "/Users/juhasch/miniforge3/envs/ros2_kilted/lib/python3.12/site-packages/numpy/core/include")

# Generate custom messages
set(MSG_FILES
  "msg/RadarPointCloud.msg"
  "msg/RadarInfo.msg"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${MSG_FILES}
  DEPENDENCIES
    std_msgs
    sensor_msgs
    geometry_msgs
)

# Install Python executables
install(PROGRAMS
  scripts/radar_publisher_node.py
  scripts/radar_replay_node.py
  scripts/radar_transform_node.py
  scripts/pointcloud2_converter.py
  scripts/check_transforms.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}/
)

# Install config files
install(DIRECTORY
  config
  DESTINATION share/${PROJECT_NAME}/
)

# Install configs directory from root level (contains user_profile.cfg and default_config.yaml)
install(DIRECTORY
  ../configs
  DESTINATION share/${PROJECT_NAME}/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package() 