import json
import logging
import time
import os
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MyMQTT import MyMQTT
from service_log import print_banner

logger = logging.getLogger(__name__)


def get_sector_from_pipeline(pipeline_id: str) -> str:
    if pipeline_id.upper().startswith("N"):
        return "sector-north"
    elif pipeline_id.upper().startswith("S"):
        return "sector-south"
    return "sector-north"


class CommandType(Enum):
    OPEN = "open"
    CLOSE = "close"
    TOGGLE = "toggle"
    CHECK = "check"


class CommandPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    EMERGENCY = 3


@dataclass
class ValveCommand:
    pipeline_id: str
    valve_id: str
    command: CommandType
    sector_id: Optional[str] = None
    source: str = "control_center"
    reason: Optional[str] = None
    priority: CommandPriority = CommandPriority.NORMAL
    timestamp: Optional[float] = None


class ValveCommander:
    def __init__(self, mqtt_broker: str, mqtt_port: int):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.client_id = "control-center-commander"
        self.mqtt_start_wait = int(os.environ["MQTT_START_WAIT"])

        self.mqtt = MyMQTT(self.client_id, self.mqtt_broker, self.mqtt_port, self)

        self.connected = False
        self.telegram_command_handler = None
        self.alert_handler = None

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)

            if topic.startswith("telegram/commands/"):
                self._handle_telegram_command(topic, data)
            elif "/alerts/" in topic:
                self._handle_analytics_alert(topic, data)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message from {topic}: {e}")
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")

    def _handle_telegram_command(self, topic: str, payload: Dict[str, Any]):
        pipeline_id = payload.get("pipeline_id")
        valve_id = payload.get("valve_id")
        action = payload.get("command")
        user_id = payload.get("user_id", "telegram_user")
        reason = f"Telegram command by {user_id}"

        if not pipeline_id or not valve_id or not action:
            logger.error(f"Invalid Telegram command - missing fields: {payload}")
            return

        logger.info(f"Received Telegram command: {action} valve {valve_id} on pipeline {pipeline_id} from {user_id}")

        if self.telegram_command_handler:
            success = self.telegram_command_handler(pipeline_id, valve_id, action, reason, source="telegram_user")
            logger.info(f"Telegram command executed: success={success}")
        else:
            if action == "open":
                self.open_valve(pipeline_id, valve_id, reason, source="telegram_user")
            elif action == "close":
                self.close_valve(pipeline_id, valve_id, reason, source="telegram_user")

    def set_telegram_command_handler(self, handler):
        self.telegram_command_handler = handler
        logger.info("Telegram command handler registered")

    def _handle_analytics_alert(self, topic, payload):
        severity = payload.get("severity")
        alert_type = payload.get("alert_type")
        fast_track = (
            severity == "critical"
            or (alert_type == "anomaly" and severity in ("high", "critical"))
        )
        if not fast_track:
            return

        pipeline_id = payload.get("pipeline_id")
        bolt_id = payload.get("bolt_id")
        if not pipeline_id or not bolt_id:
            logger.warning(f"Alert missing pipeline_id or bolt_id: {payload}")
            return

        if self.alert_handler:
            self.alert_handler(pipeline_id, bolt_id, payload)

    def set_alert_handler(self, handler):
        self.alert_handler = handler
        logger.info("Analytics alert handler registered")

    def connect(self) -> bool:
        try:
            self.mqtt.start()
            time.sleep(self.mqtt_start_wait)
            self.connected = True

            self.mqtt.mySubscribe("telegram/commands/+")
            self.mqtt.mySubscribe("sectors/+/pipelines/+/alerts/+")
            logger.info(f"Valve Commander connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        self.mqtt.stop()
        self.connected = False
        logger.info("Valve Commander disconnected")

    def send_command(self, command: ValveCommand) -> bool:
        try:
            if not self.connected:
                logger.error("Not connected to MQTT broker")
                return False

            command.timestamp = command.timestamp or time.time()
            if command.sector_id is None:
                command.sector_id = get_sector_from_pipeline(command.pipeline_id)

            payload = {
                "command": command.command.value,
                "pipeline_id": command.pipeline_id,
                "valve_id": command.valve_id,
                "sector_id": command.sector_id,
                "source": command.source,
                "timestamp": command.timestamp,
                "priority": command.priority.value
            }
            if command.reason:
                payload["reason"] = command.reason

            topic = f"sectors/{command.sector_id}/pipelines/{command.pipeline_id}/commands/valves"
            self.mqtt.myPublish(topic, payload)

            logger.info(f"Valve command sent: {command.valve_id} -> {command.command.value} on pipeline {command.pipeline_id}")
            print_banner(
                "VALVE COMMAND",
                [
                    f"valve: {command.valve_id} -> {command.command.value}",
                    f"pipe:  {command.pipeline_id}",
                    f"src:   {command.source}",
                    f"why:   {command.reason or '-'}",
                ],
                kind="warning" if command.priority == CommandPriority.EMERGENCY else "success",
            )
            return True

        except Exception as e:
            logger.error(f"Error sending valve command: {e}")
            return False

    def open_valve(self, pipeline_id: str, valve_id: str, reason: Optional[str] = None, sector_id: Optional[str] = None, source: str = "control_center") -> bool:
        command = ValveCommand(
            pipeline_id=pipeline_id,
            valve_id=valve_id,
            command=CommandType.OPEN,
            sector_id=sector_id,
            reason=reason,
            source=source,
        )
        return self.send_command(command)

    def close_valve(self, pipeline_id: str, valve_id: str, reason: Optional[str] = None, sector_id: Optional[str] = None, source: str = "control_center") -> bool:
        command = ValveCommand(
            pipeline_id=pipeline_id,
            valve_id=valve_id,
            command=CommandType.CLOSE,
            sector_id=sector_id,
            reason=reason,
            source=source,
        )
        return self.send_command(command)

    def emergency_closure(self, pipeline_id: str, valve_ids: List[str], reason: str, sector_id: Optional[str] = None) -> Dict[str, bool]:
        results = {}
        for valve_id in valve_ids:
            command = ValveCommand(
                pipeline_id=pipeline_id,
                valve_id=valve_id,
                command=CommandType.CLOSE,
                sector_id=sector_id,
                reason=f"EMERGENCY: {reason}",
                priority=CommandPriority.EMERGENCY
            )
            results[valve_id] = self.send_command(command)

        logger.warning(f"Emergency closure executed for {len(valve_ids)} valves on pipeline {pipeline_id}")
        return results

