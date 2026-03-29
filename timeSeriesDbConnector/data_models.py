# data models for sensor readings, valves, anomalies
# from python dataclasses docs

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class DataType(Enum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    VALVE_STATUS = "valve_status"
    ANOMALY = "anomaly"

class AggregationType(Enum):
    MEAN = "mean"
    MAX = "max"
    MIN = "min"
    COUNT = "count"
    STDDEV = "stddev"
    LAST = "last"
    FIRST = "first"

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

@dataclass
class TimeSeriesQuery:
    measurement: DataType
    pipeline_id: Optional[str] = None
    bolt_id: Optional[str] = None
    valve_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100
    aggregation: Optional[AggregationType] = None
    group_by_time: Optional[str] = None

@dataclass
class QueryResult:
    query: TimeSeriesQuery
    data: List[Dict[str, Any]]
    count: int
    execution_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": {
                "measurement": self.query.measurement.value,
                "pipeline_id": self.query.pipeline_id,
                "bolt_id": self.query.bolt_id,
                "limit": self.query.limit,
                "aggregation": self.query.aggregation.value if self.query.aggregation else None
            },
            "data": self.data,
            "count": self.count,
            "execution_time": self.execution_time
        }

@dataclass
class Statistics:
    # stats for dashboard display
    mean: float
    min: float
    max: float
    stddev: float
    count: int
    last_value: float
    last_timestamp: float

    def to_dict(self):
        # round everything for display
        return {
            "mean": round(self.mean, 2),
            "min": round(self.min, 2),
            "max": round(self.max, 2),
            "stddev": round(self.stddev, 2),
            "count": self.count,
            "last_value": round(self.last_value, 2),
            "last_timestamp": self.last_timestamp
        }

@dataclass
class PipelineSummary:
    pipeline_id: str
    total_bolts: int
    active_bolts: int
    last_update: float
    temperature_stats: Optional[Statistics] = None
    pressure_stats: Optional[Statistics] = None
    anomaly_count: int = 0
    valve_states: Dict[str, str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "total_bolts": self.total_bolts,
            "active_bolts": self.active_bolts,
            "last_update": self.last_update,
            "temperature_stats": self.temperature_stats.to_dict() if self.temperature_stats else None,
            "pressure_stats": self.pressure_stats.to_dict() if self.pressure_stats else None,
            "anomaly_count": self.anomaly_count,
            "valve_states": self.valve_states or {}
        }