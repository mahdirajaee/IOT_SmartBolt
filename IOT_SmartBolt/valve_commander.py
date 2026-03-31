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
    def __init__(self, mqtt_broker: str = "localhost", mqtt_port: int = 1883):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.client_id = "control-center-commander"

        self.mqtt = MyMQTT(self.client_id, self.mqtt_broker, self.mqtt_port, self)

        self.connected = False
        self.command_history = []
        self.max_history = 1000
        self.command_stats = {
            "sent": 0,
            "failed": 0,
            "by_type": {},
            "by_pipeline": {},
            "telegram_commands_received": 0
        }
        self.telegram_command_handler = None

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)

            if topic.startswith("telegram/commands/"):
                self._handle_telegram_command(topic, data)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message from {topic}: {e}")
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")

    def _handle_telegram_command(self, topic: str, payload: Dict[str, Any]):
        self.command_stats["telegram_commands_received"] += 1

        pipeline_id = payload.get("pipeline_id")
        valve_id = payload.get("valve_id")
        action = payload.get("command")
        user_id = payload.get("user_id", "telegram_user")
        reason = f"Telegram command by {user_id}"

        if not all([pipeline_id, valve_id, action]):
            logger.error(f"Invalid Telegram command - missing fields: {payload}")
            return

        logger.info(f"Received Telegram command: {action} valve {valve_id} on pipeline {pipeline_id} from {user_id}")

        if self.telegram_command_handler:
            success = self.telegram_command_handler(pipeline_id, valve_id, action, reason)
            logger.info(f"Telegram command executed: success={success}")
        else:
            if action == "open":
                self.open_valve(pipeline_id, valve_id, reason)
            elif action == "close":
                self.close_valve(pipeline_id, valve_id, reason)

    def set_telegram_command_handler(self, handler):
        self.telegram_command_handler = handler
        logger.info("Telegram command handler registered")

    def connect(self) -> bool:
        try:
            self.mqtt.start()
            time.sleep(1)
            self.connected = True

            self.mqtt.mySubscribe("telegram/commands/+")
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
            self._update_stats(command, success=True)
            self._add_to_history(command)
            return True

        except Exception as e:
            logger.error(f"Error sending valve command: {e}")
            self._update_stats(command, success=False)
            return False

    def open_valve(self, pipeline_id: str, valve_id: str, reason: Optional[str] = None, sector_id: Optional[str] = None) -> bool:
        command = ValveCommand(
            pipeline_id=pipeline_id,
            valve_id=valve_id,
            command=CommandType.OPEN,
            sector_id=sector_id,
            reason=reason
        )
        return self.send_command(command)

    def close_valve(self, pipeline_id: str, valve_id: str, reason: Optional[str] = None, sector_id: Optional[str] = None) -> bool:
        command = ValveCommand(
            pipeline_id=pipeline_id,
            valve_id=valve_id,
            command=CommandType.CLOSE,
            sector_id=sector_id,
            reason=reason
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

    def batch_command(self, commands: List[ValveCommand]) -> Dict[str, bool]:
        results = {}
        for command in commands:
            key = f"{command.pipeline_id}_{command.valve_id}"
            results[key] = self.send_command(command)
        return results

    def _update_stats(self, command: ValveCommand, success: bool):
        key = "sent" if success else "failed"
        self.command_stats[key] += 1

        cmd_type = command.command.value
        self.command_stats["by_type"].setdefault(cmd_type, {"sent": 0, "failed": 0})
        self.command_stats["by_type"][cmd_type][key] += 1

        self.command_stats["by_pipeline"].setdefault(command.pipeline_id, 0)
        self.command_stats["by_pipeline"][command.pipeline_id] += 1

    def _add_to_history(self, command: ValveCommand):
        self.command_history.append({
            "pipeline_id": command.pipeline_id,
            "valve_id": command.valve_id,
            "command": command.command.value,
            "reason": command.reason,
            "priority": command.priority.value,
            "timestamp": command.timestamp
        })

        if len(self.command_history) > self.max_history:
            self.command_history = self.command_history[-self.max_history:]

    def get_stats(self) -> Dict[str, Any]:
        return self.command_stats.copy()

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.command_history[-limit:]

    def clear_history(self):
        self.command_history.clear()
        logger.info("Command history cleared")
