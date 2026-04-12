import json
import logging
import time
import os
import sys
from typing import Dict, Any, Callable, List
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MyMQTT import MyMQTT

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class Alert:
    alert_type: str
    pipeline_id: str
    message: str
    severity: AlertSeverity
    timestamp: float
    data: Dict[str, Any]


class MQTTClient:
    def __init__(self, broker: str = "localhost", port: int = 1883):
        self.broker = broker
        self.port = port
        self.client_id = "telegram-bot-mqtt"

        self.mqtt = MyMQTT(self.client_id, self.broker, self.port, self)

        self.connected = False
        self.alert_handlers: List[Callable] = []

        self._recent_alert_keys = {}
        self._dedup_window = 2

        self.pending_commands = {}
        self.valve_ack_handlers: List[Callable] = []

        self.stats = {
            "alerts_received": 0,
            "commands_sent": 0,
            "errors": 0,
            "start_time": time.time()
        }

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)
            logger.debug(f"Received message on {topic}")

            if topic == "events/valve_changed" or topic.startswith("events/valve_changed"):
                self._handle_valve_ack(data)
            elif "/alerts/" in topic or topic.startswith("alerts/"):
                self._handle_alert(topic, data)
                self.stats["alerts_received"] += 1

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message from {topic}: {e}")
            self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")
            self.stats["errors"] += 1

    def _handle_alert(self, topic: str, payload: Dict[str, Any]):
        severity = self._determine_severity(payload)
        pipeline_id = payload.get("pipeline_id", "unknown")
        alert_type = payload.get("alert_type") or payload.get("anomaly_type", "unknown")
        timestamp = payload.get("timestamp", time.time())

        dedup_key = f"{pipeline_id}_{alert_type}_{severity.value}_{int(timestamp)}"
        now = time.time()

        if dedup_key in self._recent_alert_keys and now - self._recent_alert_keys[dedup_key] < self._dedup_window:
            return

        self._recent_alert_keys[dedup_key] = now

        if len(self._recent_alert_keys) > 200:
            cutoff = now - self._dedup_window * 2
            self._recent_alert_keys = {k: v for k, v in self._recent_alert_keys.items() if v > cutoff}

        message = payload.get("message") or payload.get("description", "Alert received")

        alert = Alert(
            alert_type=alert_type,
            pipeline_id=pipeline_id,
            message=message,
            severity=severity,
            timestamp=timestamp,
            data=payload
        )

        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")

    def _determine_severity(self, payload: Dict[str, Any]) -> AlertSeverity:
        severity_str = payload.get("severity", "info").lower()
        alert_type = (payload.get("alert_type") or payload.get("anomaly_type", "")).lower()

        severity_map = {
            "emergency": AlertSeverity.EMERGENCY,
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.ALERT,
            "alert": AlertSeverity.ALERT,
            "warning": AlertSeverity.WARNING,
            "medium": AlertSeverity.WARNING,
        }
        type_map = {
            "threshold_exceeded": AlertSeverity.CRITICAL,
            "anomaly": AlertSeverity.ALERT,
            "threshold_warning": AlertSeverity.WARNING,
            "prediction_warning": AlertSeverity.WARNING,
        }

        result = severity_map.get(severity_str) or type_map.get(alert_type, AlertSeverity.INFO)

        if result == AlertSeverity.CRITICAL and payload.get("exceeded_by", 0) > 20:
            return AlertSeverity.EMERGENCY

        return result

    def add_alert_handler(self, handler: Callable[[Alert], None]):
        self.alert_handlers.append(handler)
        logger.info("Alert handler registered")

    def connect(self) -> bool:
        try:
            self.mqtt.start()
            time.sleep(1)
            self.connected = True

            self.mqtt.mySubscribe("sectors/+/pipelines/+/alerts/+")
            self.mqtt.mySubscribe("alerts/anomalies/+")
            self.mqtt.mySubscribe("events/valve_changed")

            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        self.mqtt.stop()
        self.connected = False
        logger.info("MQTT client disconnected")

    def send_valve_command(self, pipeline_id: str, valve_id: str, action: str, user_id: str = None) -> bool:
        command = {
            "command": action,
            "pipeline_id": pipeline_id,
            "valve_id": valve_id,
            "source": "telegram_bot",
            "timestamp": time.time()
        }
        if user_id:
            command["user_id"] = user_id

        try:
            topic = f"telegram/commands/{pipeline_id}"
            self.mqtt.myPublish(topic, command)
            self.stats["commands_sent"] += 1
            logger.info(f"Valve command sent: {action} {valve_id} on {pipeline_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending valve command: {e}")
            self.stats["errors"] += 1
            return False

    def request_pipeline_status(self, pipeline_id: str) -> bool:
        command = {
            "request": "status",
            "pipeline_id": pipeline_id,
            "timestamp": time.time()
        }
        try:
            self.mqtt.myPublish(f"telegram/commands/status/{pipeline_id}", command)
            return True
        except Exception:
            return False

    def _handle_valve_ack(self, payload: Dict[str, Any]):
        inner = payload.get("data", payload)
        pipeline_id = inner.get("pipeline_id")
        valve_id = inner.get("valve_id")
        success = inner.get("success", False)
        key = f"{pipeline_id}_{valve_id}"

        if key in self.pending_commands:
            cmd = self.pending_commands.pop(key)
            if cmd.get("callback"):
                try:
                    cmd["callback"](pipeline_id, valve_id, success)
                except Exception as e:
                    logger.error(f"Error in valve ack callback: {e}")

        for handler in self.valve_ack_handlers:
            try:
                handler(pipeline_id, valve_id, success)
            except Exception as e:
                logger.error(f"Error in valve ack handler: {e}")

    def register_pending_command(self, pipeline_id: str, valve_id: str, callback: Callable, timeout: float = 15):
        key = f"{pipeline_id}_{valve_id}"
        self.pending_commands[key] = {
            "callback": callback,
            "timestamp": time.time(),
            "timeout": timeout
        }

    def check_command_timeouts(self):
        now = time.time()
        expired = [
            key for key, cmd in self.pending_commands.items()
            if now - cmd["timestamp"] > cmd["timeout"]
        ]
        for key in expired:
            cmd = self.pending_commands.pop(key)
            if cmd.get("callback"):
                parts = key.split("_", 1)
                try:
                    cmd["callback"](parts[0] if parts else "unknown", parts[1] if len(parts) > 1 else "unknown", None)
                except Exception as e:
                    logger.error(f"Error in timeout callback: {e}")

    def get_stats(self) -> Dict[str, Any]:
        uptime = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "connected": self.connected
        }

    def get_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.connected else "disconnected",
            "timestamp": time.time(),
            "stats": self.get_stats()
        }
