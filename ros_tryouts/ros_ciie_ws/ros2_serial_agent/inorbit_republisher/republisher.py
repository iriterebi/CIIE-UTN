#!/usr/bin/env python

# Copyright 2021 InOrbit, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# ROS to InOrbit republisher node sample
#
# It uses a YAML-based configuration to map between arbitrary
# ROS topics into InOrbit key/value custom data topics.

import json
import rclpy
from rosidl_runtime_py.utilities import get_message
import yaml
import os
from std_msgs.msg import String
from builtin_interfaces.msg import Time
from operator import attrgetter

# Types of mappings allowed
MAPPING_TYPE_SINGLE_FIELD = "single_field"
MAPPING_TYPE_ARRAY_OF_FIELDS = "array_of_fields"
MAPPING_TYPE_JSON_OF_FIELDS = "json_of_fields"

# Supported static publisher value sources
STATIC_VALUE_FROM_PACKAGE_VERSION = "package_version"
STATIC_VALUE_FROM_ENVIRONMENT_VAR = "environment_variable"

"""
Custom JSON encoder to deal with types found on ROS 2 messages that are not
serializable to string by default.
For now this includes:
 - bytes objects to decoded String objects
"""
class ROS2JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return obj.decode()
        return json.JSONEncoder.default(self, obj)

"""
Main node entry point.

Currently a simple function that does everything.
We can later turn it into a class and divide in proper methods
as complexity increases.
"""
def main(args = None):
    # Start the ROS node
    rclpy.init(args=args)
    node = rclpy.create_node('inorbit_republisher')
    # Declares the "config" parameter, it contains the path of the config file
    node.declare_parameter('config')
    # Read republisher configuration from the 'config_file' or 'config' parameter
    # TODO(adamantivm) Error handling and schema checking
    if node.has_parameter('config'):
        config_file = node.get_parameter(
            'config').get_parameter_value().string_value
        node.get_logger().info("Using config from config file: {}".format(config_file))
        config_yaml = open(config_file, "r")
    config = yaml.safe_load(config_yaml)

    # Go through republisher configurations
    # For each of them: create a publisher if necessary - only one per InOrbit
    # custom data field - and a matching subscriber to receive and republish
    # the desired fields.

    # Dictionary of publisher instances by topic name
    pubs = {}

    # Dictionary of subscriber instances by topic name
    subs = {}

    # TODO(adamantivm) Port ability to publish package versions from ROS 1 Noetic to ROS 2 Foxy
    # # In case we want to query ROS package options
    # rospack = rospkg.RosPack()

    # Set-up ROS topic republishers
    republishers = config.get('republishers', ())
    for repub in republishers:

        # Load subscriber message type
        msg_class = get_message(repub['msg_type'])
        if msg_class is None:
            node.get_logger().warning('Failed to load msg class for {}'.format(repub['msg_type']))
            continue

        # Create publisher for each new seen outgoing topic
        for mapping in repub['mappings']:
            out_topic = mapping['out']['topic']
            if not out_topic in pubs:
                # NOTE(adamantivm) Using QOS = 10 to match InOrbit Custom Data topic spec
                pubs[out_topic] = node.create_publisher(String, out_topic, 10)
            mapping['attrgetter'] = attrgetter(mapping['field'])

        # Prepare callback to relay messages through InOrbit custom data
        def callback(msg, repub=repub):

            for mapping in repub['mappings']:
                key = mapping['out']['key']
                val = None
                mapping_type = mapping.get('mapping_type', MAPPING_TYPE_SINGLE_FIELD)
                topic = mapping['out']['topic']

                if mapping_type == MAPPING_TYPE_SINGLE_FIELD:
                    # TODO(adamantivm) Exception handling
                    field = extract_value(msg, attrgetter(mapping['field']))
                    val = process_single_field(field, mapping)
                    # Time values can't be cleanly serialized into JSON. convert them to milliseconds
                    if isinstance(val, Time):
                        val = rclpy.time.Time.from_msg(val).nanoseconds / 1000000

                elif mapping_type == MAPPING_TYPE_ARRAY_OF_FIELDS:
                    field = extract_value(msg, attrgetter(mapping['field']))
                    val = process_array(field, mapping)

                elif mapping_type == MAPPING_TYPE_JSON_OF_FIELDS:
                    try:
                        val = extract_values_as_dict(msg, mapping, node)
                        # extract_values_as_dict has the ability to filter messages and
                        # returns None when an element doesn't pass the filter
                        if val:
                          val = json.dumps(val, cls=ROS2JSONEncoder)
                    except TypeError as e:
                        node.get_logger().warning(f"Failed to serialize message: {e}")

                if val is not None:
                    pubs[topic].publish(String(data=f"{key}={val}"))

        in_topic = repub['topic']
        # Reads QoS from the topic settings
        in_qos = getattr(repub, 'qos', 10)

        # subscribe
        subs[in_topic] = node.create_subscription(msg_class, in_topic, callback, in_qos)

    # Set-up static publishers
    static_publishers = config.get('static_publishers', ())
    for static_pub_config in static_publishers:
        key = static_pub_config['out']['key']
        topic = static_pub_config['out']['topic']

        # If a literal value is provided, it takes highest precendence
        val = static_pub_config.get('value')

        # Otherwise, fetch the value from the specified source
        if val is None:
            value_from = static_pub_config.get('value_from')
            if STATIC_VALUE_FROM_ENVIRONMENT_VAR in value_from:
                var_name = value_from[STATIC_VALUE_FROM_ENVIRONMENT_VAR]
                val = os.environ.get(var_name)
            # TODO(adamantivm) Implement publishing of package version for ROS 2
            # elif STATIC_VALUE_FROM_PACKAGE_VERSION in value_from:
            #     pkg_name = value_from[STATIC_VALUE_FROM_PACKAGE_VERSION]
            #     # TODO(adamantivm) Exception handling
            #     pkg_manifest = rospack.get_manifest(pkg_name)
            #     val = pkg_manifest.version

        # If there is a value to publish, publish it using once per subscriber
        # TODO(adamantivm) Make these values latched
        if val is not None:
            pub = node.create_publisher(String, topic, 10)
            pub.publish(String(data=f"{key}={val}"))

    node.get_logger().info("Republisher started")
    rclpy.spin(node)
    node.get_logger().info("Republisher shutting down")

    node.destroy_node()
    rclpy.shutdown()
    node.get_logger().info("Shutdown complete")

"""
Extracts a value from the given message using the provided getter function
"""
def extract_value(msg, getter_fn):
    # TODO(adamantivm) Graceful handling of missing values to extract
    # TODO(adamantivm) Allow serialization of complex values
    val = getter_fn(msg)
    return val


"""
Extracts several values from a given nested msg field and returns a dictionary of
<field, value> elements
"""
# TODO(elvioaruta): after refactoring and using Node as classes
# remove the node from this function and figure out a better way
# to log warnings inside
def extract_values_as_dict(msg, mapping, node):
    values = {}
    base_getter_fn = attrgetter(mapping['field'])
    base_value = base_getter_fn(msg)
    fields = mapping.get('mapping_options', {}).get('fields')
    for field in fields:
        getter_fn = attrgetter(field)
        try:
            val = getter_fn(base_value)
            # Time values aren't cleanly serialized into JSON.
            # Convert them to milliseconds
            if isinstance(val, Time):
                val = rclpy.time.Time.from_msg(val).nanoseconds / 1000000
            # TODO(diegobatt): Make it possible to use a different key than the field
            values[field] = val
        except AttributeError as e:
            node.get_logger().warning(f"Couldn\'t get attribute {field}: {e}")
    filter_fn = mapping.get('mapping_options', {}).get('filter')
    return values if not filter_fn or eval(filter_fn)(values) else None

"""
Processes a scalar value before publishing according to mapping options
 - If a 'filter' function is provided, it returns the value only if the
   result of passing the field value through the filter function is True,
   otherwise it returns None
"""
def process_single_field(field_value, mapping):
    filter_fn = mapping.get('mapping_options', {}).get('filter')
    return field_value if not filter_fn or eval(filter_fn)(field_value) else None

"""
Processes a given array field from the ROS message and:
    - Filters it using the 'filter' function (if provided)
    - For each element, it gets the set of keys defined by array_fields
    - Returns a key/value with the value being a json string containing
      the resulting array of objects.

Note that the array fields to retrieve should have a String value in order to
serialize them properly.
"""
def process_array(field, mapping):
    # Output array of objects
    values = {
        'data': []
    }

    filter_fn = mapping.get('mapping_options', {}).get('filter')
    if filter_fn:
        # Apply the filter function if any
        filtered_array = list(filter(eval(filter_fn), field))
    else:
        filtered_array = field

    # Get only the array_fields specified. If none was specified, return the whole array
    # TODO(FlorGrosso): check that the array fields are Strings and discard those  which
    # are not.
    if 'fields' in mapping.get('mapping_options', {}):
        fields = mapping['mapping_options']['fields']
        values['data'] = [{f: extract_value(elem, attrgetter(f)) for f in fields} for elem in filtered_array]
    else:
        values['data'] = filtered_array
    return json.dumps(values, cls=ROS2JSONEncoder)

if __name__ == '__main__':
    main()