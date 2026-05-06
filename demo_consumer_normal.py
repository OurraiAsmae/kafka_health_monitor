"""
Consumer normal — reste connecté en permanence.
Lit 20 messages par seconde → suit la production.
"""
import time
from confluent_kafka import Consumer, KafkaError

consumer = Consumer({
    "bootstrap.servers": "kafka:29092",
    "group.id": "normal-consumer-group",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": True,
    "auto.commit.interval.ms": 1000,
})

consumer.subscribe(["clicks", "events"])
print("[normal-consumer] Demarre sur clicks + events")

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            print(f"[normal-consumer] Erreur: {msg.error()}")
            continue
        print(f"[normal-consumer] offset={msg.offset()} topic={msg.topic()}")
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    consumer.close()