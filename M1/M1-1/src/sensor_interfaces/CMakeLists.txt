cmake_minimum_required(VERSION 3.8)
project(sensor_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)

# 把 msg/SensorData.msg 编译成能 import 的消息类型
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/SensorData.msg"
  "srv/TriggerAlarm.srv"
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
