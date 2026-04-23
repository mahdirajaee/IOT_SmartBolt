import json
import logging
import time
import os
import sys
from typing import Callable

from data_models import SensorReading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MyMQTT import MyMQTT

logger = logging.getLogger(__name__)


class MQTTSubscriber:

    def __init__(self, broker="localhost", port=1883):
        self.broker = broker
        self.port = port
        self.client_id = "timeseries-db-subscriber"

        self.mqtt = MyMQTT(self.client_id, self.broker, self.port, self, clean_session=False)

        self.storage_callback = None

        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "messages_failed": 0,
            "by_topic": {},
            "start_time": time.time()
        }

    def notify(self, topic, payload):
        try:
            self.stats["messages_received"] += 1

            base_topic = topic.split("/")[0] if "/" in topic else topic
            if base_topic not in self.stats["by_topic"]:
                self.stats["by_topic"][base_topic] = 0
            self.stats["by_topic"][base_topic] += 1

            data = json.loads(payload)
            self._handle_message(topic, data)
            self.stats["messages_processed"] += 1

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message from {topic}: {e}")
            self.stats["messages_failed"] += 1
        except Exception as e:
            logger.error(f"Error handling message from {topic}: {e}")
            self.stats["messages_failed"] += 1

    def _handle_message(self, topic, data):
        if "/measurements" in topic:
            self._handle_sensor_data(data)
        else:
            logger.debug(f"Unrecognized topic pattern: {topic}")

    def _parse_senml(self, data):
        bn = data.get("bn", "")
        bt = data.get("bt", time.time())
        entries = data.get("e", [])

        parts = bn.strip("/").split("/")
        if len(parts) < 4:
            logger.warning(f"Unexpected SenML bn format (expected sectors/X/pipelines/Y): '{bn}'")
        sector_id = parts[1] if len(parts) >= 2 else "sector-unknown"
        pipeline_id = parts[3] if len(parts) >= 4 else "unknown"

        bolts = {}

        for entry in entries:
            name = entry.get("n", "")
            name_parts = name.split("/")
            if len(name_parts) < 2:
                continue

            device_id = name_parts[0]
            field = name_parts[1]
            value = entry.get("v", entry.get("vb", entry.get("vs")))

            if device_id.startswith("bolt_"):
                if device_id not in bolts:
                    bolts[device_id] = {}
                bolts[device_id][field] = value

        return pipeline_id, sector_id, bt, bolts

    def _handle_sensor_data(self, data):
        pipeline_id, sector_id, timestamp, bolts = self._parse_senml(data)

        for bolt_id, readings in bolts.items():
            sensor_reading = SensorReading(
                pipeline_id=pipeline_id,
                bolt_id=bolt_id,
                timestamp=timestamp,
                temperature=readings.get("temperature"),
                pressure=readings.get("pressure"),
                sector_id=sector_id
            )
            if self.storage_callback:
                self.storage_callback("sensor", sensor_reading)

    def set_storage_callback(self, callback: Callable):
        self.storage_callback = callback

    def start(self) -> bool:
        try:
            self.mqtt.start()
            time.sleep(1)

            self.mqtt.mySubscribe("sectors/+/pipelines/+/measurements")

            logger.info("MQTT Subscriber started - subscribed directly to RPi topics")
            return True
        except Exception as e:
            logger.error(f"Error starting MQTT subscriber: {e}")
            return False

    def stop(self):
        logger.info("Stopping MQTT subscriber...")
        self.mqtt.stop()
        logger.info("MQTT subscriber stopped")

    def get_stats(self):
        uptime = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "messages_per_minute": (self.stats["messages_received"] / uptime) * 60 if uptime > 0 else 0,
            "queue_size": 0,
            "connected": self.mqtt.connected
        }
