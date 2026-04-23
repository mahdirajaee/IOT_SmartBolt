import json
import logging
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MyMQTT import MyMQTT

logger = logging.getLogger(__name__)


class MQTTPublisher:

    def __init__(self, broker, port, client_id=None):
        self.broker = broker
        self.port = port
        self.sector_id = os.getenv("SECTOR_ID", "sector-south")
        self.client_id = client_id or f"raspberrypi-{self.sector_id}-{int(time.time())}"
        self.mqtt_topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", "sectors")

        self.mqtt = MyMQTT(self.client_id, self.broker, self.port, self)

        self.connected = False
        self.command_handlers = {}

        self.stats = {
            "messages_published": 0,
            "messages_failed": 0,
            "commands_received": 0,
            "connection_attempts": 0,
            "last_publish_time": None,
            "last_command_time": None
        }

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)
            self.stats["commands_received"] += 1
            self.stats["last_command_time"] = time.time()

            for pattern, handler in self.command_handlers.items():
                if self._topic_matches(pattern, topic):
                    handler(topic, data)
                    return

            logger.debug(f"No handler for topic: {topic}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def connect(self):
        try:
            self.stats["connection_attempts"] += 1
            self.mqtt.start()
            time.sleep(1)
            self.connected = True

            self._subscribe_to_commands()
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        self.mqtt.stop()
        self.connected = False
        logger.info("Disconnected from MQTT broker")

    def _to_senml(self, data):
        pipeline_id = data.get("pipeline_id")
        sector_id = data.get("sector_id", self.sector_id)
        timestamp = data.get("timestamp", time.time())
        bolt_data = data.get("bolt_data", {})
        valve_status = data.get("valve_status", {})

        senml = {
            "bn": f"sectors/{sector_id}/pipelines/{pipeline_id}/",
            "bt": timestamp,
            "e": []
        }

        for bolt_id, readings in bolt_data.items():
            senml["e"].append({"n": f"{bolt_id}/temperature", "u": "Cel", "v": readings.get("temperature", 0)})
            senml["e"].append({"n": f"{bolt_id}/pressure", "u": "PSI", "v": readings.get("pressure", 0)})

        for valve_id, status in valve_status.items():
            state = status.get("state") if isinstance(status, dict) else status
            senml["e"].append({"n": f"{valve_id}/state", "vs": state})

        return senml

    def publish_sensor_data(self, data, topic=None):
        try:
            pipeline_id = data.get('pipeline_id')
            if not pipeline_id:
                logger.error("No pipeline_id in data, cannot publish")
                return False

            new_topic = f"{self.mqtt_topic_prefix}/{self.sector_id}/pipelines/{pipeline_id}/measurements"
            senml_data = self._to_senml(data)
            self.mqtt.myPublish(new_topic, senml_data)

            self.stats["messages_published"] += 1
            self.stats["last_publish_time"] = time.time()
            logger.debug(f"Published SenML to {new_topic}: Pipeline {pipeline_id}")
            return True
        except Exception as e:
            logger.error(f"Error publishing sensor data: {e}")
            self.stats["messages_failed"] += 1
            return False

    def publish_event(self, event_type, event_data):
        topic = f"events/{event_type}"
        data = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": event_data
        }
        self.mqtt.myPublish(topic, data)

    def register_command_handler(self, topic_pattern, handler):
        self.command_handlers[topic_pattern] = handler
        logger.debug(f"Registered handler for pattern: {topic_pattern}")

    def _subscribe_to_commands(self):
        sector_valve_topic = f"sectors/{self.sector_id}/pipelines/+/commands/valves"
        self.mqtt.mySubscribe(sector_valve_topic)

    def _topic_matches(self, pattern, topic):
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        if len(pattern_parts) != len(topic_parts):
            return False

        for p, t in zip(pattern_parts, topic_parts):
            if p != "+" and p != t:
                return False

        return True

    def get_statistics(self):
        return {
            **self.stats,
            "connected": self.connected,
            "client_id": self.client_id
        }

    def is_connected(self):
        return self.connected
