import pika
import json
from collections import defaultdict
import os
from  network_graph import draw_network_graph

# RabbitMQ Configuration
rabbitmq_host = 'localhost'
metrics_queue = 'controller'

# Threshold for load balancing
load_threshold = 50
latency_threshold = 300 # Example latency threshold
expected_controllers = {"1", "2", "3"} 
controllers = defaultdict(dict)  # To store controller metrics

def on_message(ch, method, properties, body):
    """Process incoming metrics and make load-balancing decisions."""
    global controllers

    try:
        metrics = json.loads(body)
        controller_id = metrics["controller_id"]
        # print(controller_id)
        latency = metrics["latency"]
        load = metrics["load"]
        connected_switches = metrics["connected_switches"]

        controllers[controller_id] = {
             "latency": latency,
             "load": load,
             "connected_switches": connected_switches,
        }

        # Check if we have received metrics from all controllers
        if expected_controllers.issubset(controllers.keys()):
            evaluate_load_balancing()
            draw_network_graph(controllers)
            # print(f"Received metrics: {metrics}")
            controllers.clear()  # Reset after processing
            
        # evaluate_load_balancing()
    except json.JSONDecodeError as e:
        print(f"Error decoding message: {e}")

def evaluate_load_balancing():
    """Evaluate and decide on load balancing."""
    overloaded_controllers = []
    underloaded_controllers = []
    # print("here")

    for controller_id, data in controllers.items():
        if data["latency"] > latency_threshold and data["load"] > load_threshold:
            overloaded_controllers.append(controller_id)
        else:
            underloaded_controllers.append(controller_id)

    for src in overloaded_controllers:
        if underloaded_controllers:
            dst = underloaded_controllers.pop(0)  # Get one underloaded controller
            print("here2")
            migrate_switch(src, dst)


def migrate_switch(src, dst):
    """Migrate a switch from one controller to another."""
    # Mapping of controller IDs to their respective ports
    controller_ports = {
        "1": 6653,
        "2": 6654,
        "3": 6655
    }


    if controllers[src]["connected_switches"] :
        # Take one switch to migrate
        print(len(controllers[src]["connected_switches"]))
        switch_id = controllers[src]["connected_switches"].pop(0)
        controllers[dst]["connected_switches"].append(switch_id)

        # Get the destination controller's port
        dst_port = controller_ports.get(dst)
        if not dst_port:
            print(f"Destination controller {dst} does not have a valid port.")
            return

        # Use `ovs-vsctl` to set the new controller for the switch
        command = f"sudo ovs-vsctl set-controller s{switch_id} tcp:127.0.0.1:{dst_port}"
        result = os.system(command)

        # Check if the command was successful
        if result == 0:
            print(f"Switch {switch_id} successfully migrated from {src} to {dst}.")
        else:
            print(f"Failed to migrate switch {switch_id} from {src} to {dst}.")
    else:
        print(f"No switches available to migrate from {src}.")

def start_consumer():
    """Start consuming metrics from RabbitMQ."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
    channel = connection.channel()
    channel.queue_declare(queue=metrics_queue, durable=True)

    print("Listening for metrics...")
    channel.basic_consume(queue=metrics_queue, on_message_callback=on_message, auto_ack=True)
    channel.start_consuming()

if __name__ == "__main__":
    start_consumer()