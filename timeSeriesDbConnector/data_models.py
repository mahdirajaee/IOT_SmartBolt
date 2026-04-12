# data models for sensor readings, valves, anomalies
# from python dataclasses docs

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime
from enum import Enum

class DataType(Enum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    VALVE_STATUS = "valve_status"
    ANOMALY = "anomaly"

@dataclass
class SensorReading:
    pipeline_id: str
    bolt_id: str
    timestamp: float
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    sector_id: str = "sector-unknown"

    def to_dict(self):
        return {
            "pipeline_id": self.pipeline_id,
            "bolt_id": self.bolt_id,
            "timestamp": self.timestamp,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "sector_id": self.sector_id
        }

    @classmethod
    def from_mqtt_message(cls, data):
        # factory method to create from mqtt payload
        return cls(
            pipeline_id=data.get("pipeline_id"),
            bolt_id=data.get("bolt_id"),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
            temperature=data.get("temperature"),
            pressure=data.get("pressure"),
            sector_id=data.get("sector_id", "sector-unknown")
        )

@dataclass
class ValveStatus:
    pipeline_id: str
    valve_id: str
    state: str
    timestamp: float
    sector_id: str = "sector-unknown"

    def to_dict(self):
        return {
            "pipeline_id": self.pipeline_id,
            "valve_id": self.valve_id,
            "state": self.state,
            "timestamp": self.timestamp,
            "sector_id": self.sector_id
        }

@dataclass
class AnomalyEvent:
    # anomaly detected by analytics service
    pipeline_id: str
    bolt_id: str
    anomaly_type: str
    severity: str
    description: str
    timestamp: float
    sensor_values: Dict[str, float]
    sector_id: str = "sector-unknown"

    def to_dict(self):
        return {
            "pipeline_id": self.pipeline_id,
            "bolt_id": self.bolt_id,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "timestamp": self.timestamp,
            "sensor_values": self.sensor_values,
            "sector_id": self.sector_id
        }

