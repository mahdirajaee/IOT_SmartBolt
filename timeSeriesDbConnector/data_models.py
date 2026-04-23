from dataclasses import dataclass
from typing import Optional

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
