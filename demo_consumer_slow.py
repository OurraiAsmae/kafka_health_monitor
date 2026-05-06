"""
Consumer lent — reste connecté en permanence.
Lit 2 messages par seconde → lag monte progressivement.
"""
import time
from confluent_kafka import Consumer, KafkaError

consumer = Consumer({
    "bootstrap.servers": "kafka:29092",
    "group.id": "slow-consumer-group",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": True,
    "auto.commit.interval.ms": 1000,
})

consumer.subscribe(["orders", "logs"])
print("[slow-consumer] Demarre sur orders + logs")

try:
    while True:
        msg = consumer.poll(timeout=2.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            print(f"[slow-consumer] Erreur: {msg.error()}")
            continue
        print(f"[slow-consumer] offset={msg.offset()} topic={msg.topic()}")
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    consumer.close()