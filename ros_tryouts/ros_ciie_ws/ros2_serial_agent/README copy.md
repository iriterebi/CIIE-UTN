# InOrbit republisher for ROS 2

This directory includes a republisher that allows mapping from arbitrary ROS2 values to ``InOrbit`` [custom data](https://www.inorbit.ai/faq#publish-custom-data) key/value pairs for application-specific observability.

Currently only mapping from ROS2 topics is supported. The republisher could be extended to map actions, services and parameters.

## Usage

Create a YAML config file specifying the mappings you would like to use using this format:

```yaml
  republishers:
  - topic: "/fruits_per_cubic_m"
    qos: 5
    msg_type: "fruit_msgs/msg/Citrus"
    mappings:
    - field: "num_oranges"
      mapping_type: "single_field"
      out:
        topic: "/inorbit/custom_data"
        key: "oranges"
  - topic: "/hardware/status"
    msg_type: "hw_msgs/msg/HardwareStatus"
    mappings:
    - field: "status"
      mapping_options:
        fields: ["lidar", "motor", "battery"]
        filter: 'lambda x: (x.status == 1)'
      mapping_type: "array_of_fields"
      out:
        topic: "/inorbit/custom_data"
        key: "hardware_error"
  - topic: "/cmd_vel"
    qos: 10
    msg_type: "geometry_msgs/msg/Twist"
    mappings:
    - field: "linear"
      mapping_type: "json_of_fields"
      mapping_options:
        fields: ["x", "y", "z"]
        filter: 'lambda vel: (vel["x"] > 0)'
      out:
        topic: "/inorbit/linear_vel_test"
        key: "linear_vel"
  static_publishers:
  - value: "this is a fixed string"
    out:
      topic: "/inorbit/custom_data"
      key: "greeting"
  - value_from:
      environment_variable: "PATH"
    out:
      topic: "/inorbit/custom_data"
      key: "env_path"
```

Then launch the ``republisher.py`` script passing the config file as the ``config`` param.

A suggested way to organize this is by creating the config file and launch file in your package, then the corresponding launch file would like like this:

```xml
<launch>
  <node name="inorbit_republisher" pkg="inorbit_republisher" exec="republisher">
    <param name="config" value="$(dirname)/config/example.yaml" />
  </node>
</launch>
```

## Mapping ROS2 topics

The republisher can map the ROS2 values to single field (e.g. ``'fruit=apple'``) or to an array of fields (e.g. ``'fruits=[{fruit1: apple, fruit2: orange}, {fruit1: melon, fruit2: apple}]'``). The former is useful to capture simple fields and the latter to get data from an array of values.

### Single field: mapping options

When republishing a single field, you can include a set of ``mapping_options`` for each ``mapping``. These include:

* `filter`: a lambda expression that can be used to control whether or not the value is published based on a condition. For example, if you'd like to republish only String values that are different than ``SPAMMY STRING``, you can do it with:

  ```yaml
  mapping_options:
    filter: 'lambda x: (x != "SPAMMY STRING")'
  ```

### Array of fields: mapping options

When republishing an array of fields, you can include a set of ``mapping_options`` for each ``mapping``. These include:

* `fields`: a set of fields that you'd like to capture from each array element. For example, if each array element contains the elements ``[a, c, d, e]`` and you'd like to get ``a`` and ``c`` only, you can specify it as:

  ```yaml
  mapping_options:
    fields: ["a", "c"]
  ```

  If no fields are specified, the republisher will get all the fields in each array element.

* `filter`: a lambda expression that can be used to pick certain array elements based on a condition. For example, if you'd like to republish array elements where ``c > 5`` only, you can do it with:

  ```yaml
  mapping_options:
    filter: 'lambda x: (x > 5)'
  ```

### JSON of fields: mapping options

When republishing several fields of a nested structure, this mapping type allows to bundle them together in a single JSON message instead of republishing all the fields of interest separately.

The `mapping_options` for this type include:

* `fields`: a set of fields that you'd like to capture from the nested message. For example, if your message definition looks like [Twist](http://docs.ros.org/en/api/geometry_msgs/html/msg/Twist.html):

  setting

  ```yaml
  mapping_options:
    fields: ["x", "y", "z"]
  ```

  would output a JSON object with the fields as keys with their respective values for the message

  ```text
  data: "linear_vel={\"y\": 0.00013548378774430603, \"x\": 0.0732172280550003, \"z\": 0.0}"
  ```

  * `filter`: a lambda expression that can be used to control whether or not the JSON object is published based on a condition. For example, if you'd like to republish only JSON objects that have a value for the key ``z`` different than ``0``, you can do it with:

  ```yaml
  mapping_options:
    filter: 'lambda linear_vel: (linear_vel["z"] != 0)'
  ```

## Publishing fixed values

Sometimes it is also useful to publish fixed values to facilitate fleet-wide observability. It is possible to publish environment variables, package versions or fixed values using the `static_publishers` array.

See the included example configuration in `config/example.yaml` for specific examples.

These values will be published as latched and delivered only once every time a subscriber connects to the republisher.

## Building and running locally

Find below instructions for building the package and running the node using the the code on the workspace (see also [colcon](https://colcon.readthedocs.io/en/released/reference/verb/build.html)).

### Start ROS2 docker container (optional)

You can run the commands below for building and running the republisher inside a docker container.

```bash
docker run -ti --rm \
  --workdir /root/ros2_ws/ \
  -v .:/root/ros2_ws/src/inorbit_republisher \
  osrf/ros:foxy-desktop
```

### Build

```bash
cd ~/ros2_ws
colcon build --packages-select inorbit_republisher --symlink-install
```

### Run

```bash
source install/local_setup.bash
# Using the launch file under the 'launch' directory
ros2 launch inorbit_republisher example.launch.xml
```

## TODO

* Schema validation
* Better documentation
* Error handling
* Proper logging
* Latched topic support
* Mapping of ROS parameters
