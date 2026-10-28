import aio_pika
from aio_pika import DeliveryMode, Message

from app.config import settings

QUEUE = "taskflow.jobs"


async def connect():
    return await aio_pika.connect_robust(settings.rabbitmq_url)


async def declare(channel):
    return await channel.declare_queue(QUEUE, durable=True)


async def publish(job_id: str):
    connection = await connect()
    try:
        channel = await connection.channel(publisher_confirms=True)
        await declare(channel)
        await channel.default_exchange.publish(
            Message(body=job_id.encode(), delivery_mode=DeliveryMode.PERSISTENT),
            routing_key=QUEUE,
            mandatory=True,
        )
    finally:
        await connection.close()
