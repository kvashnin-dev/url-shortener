import pika
import os
import json

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

def publish_event(event_type: str, data: dict):
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue='url_events', durable=True)
    
    message = json.dumps({"type": event_type, "data": data})
    channel.basic_publish(
        exchange='',
        routing_key='url_events',
        body=message,
        properties=pika.BasicProperties(delivery_mode=2)
    )
    connection.close()