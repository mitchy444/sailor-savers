# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0.

import argparse
from awscrt import io, http, auth
from awsiot import mqtt_connection_builder

class CommandLineUtils:
    def __init__(self, description) -> None:
        self.parser = argparse.ArgumentParser(description="Send and receive messages through and MQTT connection.")
        self.commands = {}
        self.parsed_commands = None

    def register_command(self, command_name, example_input, help_output, required=False, type=None, default=None, choices=None, action=None):
        self.commands[command_name] = {
            "name":command_name,
            "example_input":example_input,
            "help_output":help_output,
            "required": required,
            "type": type,
            "default": default,
            "choices": choices,
            "action": action
        }

    def remove_command(self, command_name):
        if command_name in self.commands.keys():
            self.commands.pop(command_name)

    def get_args(self):
        # if we have already parsed, then return the cached parsed commands
        if self.parsed_commands is not None:
            return self.parsed_commands

        # add all the commands
        for command in self.commands.values():
            if not command["action"] is None:
                self.parser.add_argument("--" + command["name"], action=command["action"], help=command["help_output"],
                    required=command["required"], default=command["default"])
            else:
                self.parser.add_argument("--" + command["name"], metavar=command["example_input"], help=command["help_output"],
                    required=command["required"], type=command["type"], default=command["default"], choices=command["choices"])

        self.parsed_commands = self.parser.parse_args()
        # Automatically start logging if it is set
        if self.parsed_commands.verbosity:
            io.init_logging(getattr(io.LogLevel, self.parsed_commands.verbosity), 'stderr')
        return self.parsed_commands

    def update_command(self, command_name, new_example_input=None, new_help_output=None, new_required=None, new_type=None, new_default=None, new_action=None):
        if command_name in self.commands.keys():
            if new_example_input:
                self.commands[command_name]["example_input"] = new_example_input
            if new_help_output:
                self.commands[command_name]["help_output"] = new_help_output
            if new_required:
                self.commands[command_name]["required"] = new_required
            if new_type:
                self.commands[command_name]["type"] = new_type
            if new_default:
                self.commands[command_name]["default"] = new_default
            if new_action:
                self.commands[command_name]["action"] = new_action

    def add_common_mqtt_commands(self):
        self.register_command(self.m_cmd_endpoint, "<str>", "The endpoint of the mqtt server not including a port.", True, str)
        self.register_command(self.m_cmd_ca_file, "<path>", "Path to AmazonRootCA1.pem (optional, system trust store used by default)", False, str)

    def add_common_proxy_commands(self):
        self.register_command(self.m_cmd_proxy_host, "<str>", "Host name of the proxy server to connect through (optional)", False, str)
        self.register_command(self.m_cmd_proxy_port, "<int>", "Port of the http proxy to use (optional, default='8080')", type=int, default=8080)

    def add_common_topic_message_commands(self):
        self.register_command(self.m_cmd_topic, "<str>", "Topic to publish, subscribe to (optional, default='test/topic').", default="test/topic")
        self.register_command(self.m_cmd_message, "<str>", "The message to send in the payload (optional, default='Hello World!').", default="Hello World!")

    def add_common_logging_commands(self):
        self.register_command(self.m_cmd_verbosity, "<Log Level>", "Logging level.", default=io.LogLevel.NoLogs.name, choices=[x.name for x in io.LogLevel])

    """
    Returns the command if it exists and has been passed to the console, otherwise it will print the help for the sample and exit the application.
    """
    def get_command_required(self, command_name, message=None):
        if hasattr(self.parsed_commands, command_name):
            return getattr(self.parsed_commands, command_name)
        else:
            self.parser.print_help()
            print("Command --" + command_name + " required.")
            if message is not None:
                print(message)
            exit()

    """
    Returns the command if it exists and has been passed to the console, otherwise it returns whatever is passed as the default.
    """
    def get_command(self, command_name, default=None):
        if hasattr(self.parsed_commands, command_name):
            return getattr(self.parsed_commands, command_name)
        return default

    def build_pkcs11_mqtt_connection(self, on_connection_interrupted, on_connection_resumed):

        pkcs11_lib_path = self.get_command_required(self.m_cmd_pkcs11_lib)
        print(f"Loading PKCS#11 library '{pkcs11_lib_path}' ...")
        pkcs11_lib = io.Pkcs11Lib(
            file=pkcs11_lib_path,
            behavior=io.Pkcs11Lib.InitializeFinalizeBehavior.STRICT)
        print("Loaded!")

        pkcs11_slot_id = None
        if (self.get_command(self.m_cmd_pkcs11_slot) != None):
            pkcs11_slot_id = int(self.get_command(self.m_cmd_pkcs11_slot))

        # Create MQTT connection
        mqtt_connection = mqtt_connection_builder.mtls_with_pkcs11(
            pkcs11_lib=pkcs11_lib,
            user_pin=self.get_command_required(self.m_cmd_pkcs11_pin),
            slot_id=pkcs11_slot_id,
            token_label=self.get_command_required(self.m_cmd_pkcs11_token),
            private_key_label=self.get_command_required(self.m_cmd_pkcs11_key),
            cert_filepath=self.get_command_required(self.m_cmd_pkcs11_cert),
            endpoint=self.get_command_required(self.m_cmd_endpoint),
            port=self.get_command("port"),
            ca_filepath=self.get_command(self.m_cmd_ca_file),
            on_connection_interrupted=on_connection_interrupted,
            on_connection_resumed=on_connection_resumed,
            client_id=self.get_command_required("client_id"),
            clean_session=False,
            keep_alive_secs=30)

    def build_websocket_mqtt_connection(self, on_connection_interrupted, on_connection_resumed):
        proxy_options = self.get_proxy_options_for_mqtt_connection()
        credentials_provider = auth.AwsCredentialsProvider.new_default_chain()
        mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
            endpoint=self.get_command_required(self.m_cmd_endpoint),
            region=self.get_command_required(self.m_cmd_signing_region),
            credentials_provider=credentials_provider,
            http_proxy_options=proxy_options,
            ca_filepath=self.get_command(self.m_cmd_ca_file),
            on_connection_interrupted=on_connection_interrupted,
            on_connection_resumed=on_connection_resumed,
            client_id=self.get_command_required("client_id"),
            clean_session=False,
            keep_alive_secs=30)
        return mqtt_connection

    def build_direct_mqtt_connection(self, on_connection_interrupted, on_connection_resumed):
        proxy_options = self.get_proxy_options_for_mqtt_connection()
        mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=self.get_command_required(self.m_cmd_endpoint),
            port=self.get_command_required("port"),
            cert_filepath=self.get_command_required(self.m_cmd_cert_file),
            pri_key_filepath=self.get_command_required(self.m_cmd_key_file),
            ca_filepath=self.get_command(self.m_cmd_ca_file),
            on_connection_interrupted=on_connection_interrupted,
            on_connection_resumed=on_connection_resumed,
            client_id=self.get_command_required("client_id"),
            clean_session=False,
            keep_alive_secs=30,
            http_proxy_options=proxy_options)
        return mqtt_connection

    def build_mqtt_connection(self, on_connection_interrupted, on_connection_resumed):
        if self.get_command(self.m_cmd_signing_region) is not None:
            return self.build_websocket_mqtt_connection(on_connection_interrupted, on_connection_resumed)
        else:
            return self.build_direct_mqtt_connection(on_connection_interrupted, on_connection_resumed)

    def get_proxy_options_for_mqtt_connection(self):
        proxy_options = None
        if self.parsed_commands.proxy_host and self.parsed_commands.proxy_port:
            proxy_options = http.HttpProxyOptions(host_name=self.parsed_commands.proxy_host, port=self.parsed_commands.proxy_port)
        return proxy_options


    # Constants for commonly used/needed commands
    m_cmd_endpoint = "endpoint"
    m_cmd_ca_file = "ca_file"
    m_cmd_cert_file = "cert"
    m_cmd_key_file = "key"
    m_cmd_proxy_host = "proxy_host"
    m_cmd_proxy_port = "proxy_port"
    m_cmd_signing_region = "signing_region"
    m_cmd_pkcs11_lib = "pkcs11_lib"
    m_cmd_pkcs11_cert = "cert"
    m_cmd_pkcs11_pin = "pin"
    m_cmd_pkcs11_token = "token_label"
    m_cmd_pkcs11_slot = "slot_id"
    m_cmd_pkcs11_key = "key_label"
    m_cmd_message = "message"
    m_cmd_topic = "topic"
    m_cmd_verbosity = "verbosity"









# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0.

from awscrt import mqtt
import sys
import threading
import time
from uuid import uuid4
import json

# This sample uses the Message Broker for AWS IoT to send and receive messages
# through an MQTT connection. On startup, the device connects to the server,
# subscribes to a topic, and begins publishing messages to that topic.
# The device should receive those same messages back from the message broker,
# since it is subscribed to that same topic.

# Parse arguments
cmdUtils = CommandLineUtils("PubSub - Send and recieve messages through an MQTT connection.")
cmdUtils.add_common_mqtt_commands()
cmdUtils.add_common_topic_message_commands()
cmdUtils.add_common_proxy_commands()
cmdUtils.add_common_logging_commands()
cmdUtils.register_command("key", "<path>", "Path to your key in PEM format.", True, str)
cmdUtils.register_command("cert", "<path>", "Path to your client certificate in PEM format.", True, str)
cmdUtils.register_command("port", "<int>", "Connection port. AWS IoT supports 433 and 8883 (optional, default=auto).", type=int)
cmdUtils.register_command("client_id", "<str>", "Client ID to use for MQTT connection (optional, default='test-*').", default="test-" + str(uuid4()))
cmdUtils.register_command("count", "<int>", "The number of messages to send (optional, default='10').", default=10, type=int)
# Needs to be called so the command utils parse the commands
cmdUtils.get_args()

received_count = 0
received_all_event = threading.Event()

# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
        resubscribe_results = resubscribe_future.result()
        print("Resubscribe results: {}".format(resubscribe_results))

        for topic, qos in resubscribe_results['topics']:
            if qos is None:
                sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    print("Received message from topic '{}': {}".format(topic, payload))
    global received_count
    received_count += 1
    if received_count == cmdUtils.get_command("count"):
        received_all_event.set()

if __name__ == '__main__':
    mqtt_connection = cmdUtils.build_mqtt_connection(on_connection_interrupted, on_connection_resumed)

    print("Connecting to {} with client ID '{}'...".format(
        cmdUtils.get_command(cmdUtils.m_cmd_endpoint), cmdUtils.get_command("client_id")))
    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print("Connected!")

    message_count = cmdUtils.get_command("count")
    message_topic = cmdUtils.get_command(cmdUtils.m_cmd_topic)
    message_string = cmdUtils.get_command(cmdUtils.m_cmd_message)

    # # Subscribe
    # print("Subscribing to topic '{}'...".format(message_topic))
    # subscribe_future, packet_id = mqtt_connection.subscribe(
    #     topic=message_topic,
    #     qos=mqtt.QoS.AT_LEAST_ONCE,
    #     callback=on_message_received)

    # subscribe_result = subscribe_future.result()
    # print("Subscribed with {}".format(str(subscribe_result['qos'])))

    # Publish message to server desired number of times.
    # This step is skipped if message is blank.
    # This step loops forever if count was set to 0.
    if message_string:
        if message_count == 0:
            print ("Sending messages until program killed")
        else:
            print ("Sending {} message(s)".format(message_count))

        publish_count = 1
        while (publish_count <= message_count) or (message_count == 0):
            message = f'{{"testy":{publish_count}}}'#"{} [{}]".format(message_string, publish_count)
            print("Publishing message to topic '{}': {}".format(message_topic, message))
            message_json = json.dumps(message)
            mqtt_connection.publish(
                topic=message_topic,
                payload=message,
                qos=mqtt.QoS.AT_LEAST_ONCE)
            time.sleep(1)
            publish_count += 1

    # Wait for all messages to be received.
    # This waits forever if count was set to 0.

    # Disconnect
    print("Disconnecting...")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
    print("Disconnected!")
