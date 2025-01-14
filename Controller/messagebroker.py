import pika
import json

def callback(ch, method, properties, body):
    # Parse the message body into a Python dictionary
    state = json.loads(body)
    
    # Print the stats received
    print("Received Stats:")
    print(f"Controller ID: {state['controller_id']}")
    print(f"Flow Count: {state['flow_count']}")
    print(f"Timestamp: {state['timestamp']}")
    print("-" * 50)

def start_message_receiver():
    # Set up the message broker (RabbitMQ in this case)
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()

    # Declare the queue where messages will be received from
    channel.queue_declare(queue='controller_states')

    # Set up a consumer on the 'controller_states' queue
    channel.basic_consume(queue='controller_states', on_message_callback=callback, auto_ack=True)

    print("Waiting for messages. To exit press CTRL+C")
    
    # Start consuming messages
    channel.start_consuming()

if __name__ == "__main__":
    start_message_receiver()
