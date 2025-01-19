
import json
import time
import pika

# Configuration
FLOW_THRESHOLD = 100  # Example threshold for overload
UNDERLOAD_THRESHOLD = 50  # Example threshold for underload
CHECK_INTERVAL = 10  # Seconds between global checks

# Global state to track controller stats
controller_stats = {}

def update_controller_stats(controller_id, flow_count, timestamp):
    """Update stats for a specific controller."""
    controller_stats[controller_id] = {
        "flow_count": flow_count,
        "timestamp": timestamp,
    }

def decide_migration():
    """Decide and return a migration plan based on current stats."""
    overloaded_controllers = [
        controller_id for controller_id, stats in controller_stats.items()
        if stats["flow_count"] > FLOW_THRESHOLD
    ]
    underloaded_controllers = [
        controller_id for controller_id, stats in controller_stats.items()
        if stats["flow_count"] < UNDERLOAD_THRESHOLD
    ]

    migration_plan = []
    if overloaded_controllers and underloaded_controllers:
        for overloaded in overloaded_controllers:
            for underloaded in underloaded_controllers:
                # Example decision: Migrate one switch from overloaded to underloaded
                migration_plan.append({
                    "from": overloaded,
                    "to": underloaded,
                    "switch_id": f"switch-{overloaded}-to-{underloaded}",  # Example switch identifier
                })
                # Assume one switch migration per overloaded controller for simplicity
                break
    return migration_plan

def execute_migration_plan(migration_plan):
    """Send migration commands to controllers."""
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='migration_commands')

    for migration in migration_plan:
        channel.basic_publish(
            exchange='',
            routing_key='migration_commands',
            body=json.dumps(migration)
        )
        print(f"Migration command sent: {migration}")
    connection.close()

def callback(ch, method, properties, body):
    """Process incoming stats from controllers."""
    try:
        stats = eval(body.decode('utf-8'))  # Parse received stats
        controller_id = stats['controller_id']
        flow_count = stats['flow_count']
        timestamp = stats['timestamp']

        print(f"Received stats: {controller_id}, Flow Count: {flow_count}, Time: {timestamp}")
        update_controller_stats(controller_id, flow_count, timestamp)
    except Exception as e:
        print(f"Error processing message: {e}")

def periodic_check():
    """Periodically check and execute migration decisions."""
    while True:
        migration_plan = decide_migration()
        if migration_plan:
            print(f"Executing migration plan: {migration_plan}")
            execute_migration_plan(migration_plan)
        else:
            print("No migration needed at this time.")
        time.sleep(CHECK_INTERVAL)

def start_broker():
    """Start the RabbitMQ consumer and periodic checker."""
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='controller_states')

    channel.basic_consume(
        queue='controller_states',
        on_message_callback=callback,
        auto_ack=True
    )

    print("Message broker is running...")
    # Start periodic check in a separate thread
    import threading
    threading.Thread(target=periodic_check, daemon=True).start()

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Broker stopped.")
    finally:
        connection.close()

if __name__ == "__main__":
    start_broker()
