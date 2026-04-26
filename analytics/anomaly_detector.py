import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class AnomalySeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    HIGH_TEMP = "high_temperature"
    LOW_TEMP = "low_temperature"
    HIGH_PRESSURE = "high_pressure"
    LOW_PRESSURE = "low_pressure"
    COMBINED_HIGH = "combined_high" 
    COMBINED_LOW = "combined_low"
    RAPID_CHANGE = "rapid_change" 
    SENSOR_FAILURE = "sensor_failure" 
    PATTERN_ANOMALY = "pattern_anomaly"

@dataclass
class Thresholds:
    temp_min: float = 20.0
    temp_normal_min: float = 25.0
    temp_normal_max: float = 40.0
    temp_max: float = 45.0
    temp_critical: float = 60.0

    pressure_min: float = 60.0
    pressure_normal_min: float = 90.0
    pressure_normal_max: float = 110.0
    pressure_max: float = 120.0
    pressure_critical: float = 150.0

    rapid_change_temp: float = 10.0
    rapid_change_pressure: float = 20.0


@dataclass
class AnomalyResult:
    is_anomaly: bool
    anomaly_type: Optional[AnomalyType]
    severity: Optional[AnomalySeverity]
    description: str
    confidence: float 
    recommendations: List[str]

class AnomalyDetector:
    def __init__(self, thresholds: Optional[Thresholds] = None):
        self.thresholds = thresholds or Thresholds()
        self.history = {}  
        self.anomaly_counts = {}
        self.last_values = {} 
        self.pattern_buffer = {}
        self.max_history_size = 100 

    
    def detect_anomaly(self,
                      pipeline_id: str,
                      bolt_id: str,
                      temperature: float,
                      pressure: float,
                      timestamp: Optional[float] = None) -> AnomalyResult:
        timestamp = timestamp or time.time()
        device_id = f"{pipeline_id}_{bolt_id}"

        self._update_history(device_id, temperature, pressure, timestamp)
        results = []

        temp_anomaly = self._check_threshold_anomaly(temperature, "temperature")
        if temp_anomaly.is_anomaly:
            results.append(temp_anomaly)

        pressure_anomaly = self._check_threshold_anomaly(pressure, "pressure")
        if pressure_anomaly.is_anomaly:
            results.append(pressure_anomaly)

        combined_anomaly = self._check_combined_anomaly(temperature, pressure)
        if combined_anomaly.is_anomaly:
            results.append(combined_anomaly)

        rapid_change_anomaly = self._check_rapid_change(device_id, temperature, pressure)
        if rapid_change_anomaly.is_anomaly:
            results.append(rapid_change_anomaly)

        pattern_anomaly = self._check_pattern_anomaly(device_id)
        if pattern_anomaly.is_anomaly:
            results.append(pattern_anomaly)

        sensor_failure = self._check_sensor_failure(temperature, pressure)
        if sensor_failure.is_anomaly:
            results.append(sensor_failure)

        if results:
            most_severe = max(results, key=lambda x: self._severity_to_int(x.severity))
            self._update_anomaly_count(device_id)
            return most_severe
        return AnomalyResult(
            is_anomaly=False,
            anomaly_type=None,
            severity=None,
            description="Normal operating conditions",
            confidence=0.95,
            recommendations=[]
        )
    
    def _check_threshold_anomaly(self, value: float, sensor_type: str) -> AnomalyResult:
        if sensor_type == "temperature":
            critical = self.thresholds.temp_critical
            alert = self.thresholds.temp_max
            normal_max = self.thresholds.temp_normal_max
            min_val = self.thresholds.temp_min
            normal_min = self.thresholds.temp_normal_min
            high_type, low_type = AnomalyType.HIGH_TEMP, AnomalyType.LOW_TEMP
            unit = "°C"
        else:
            critical = self.thresholds.pressure_critical
            alert = self.thresholds.pressure_max
            normal_max = self.thresholds.pressure_normal_max
            min_val = self.thresholds.pressure_min
            normal_min = self.thresholds.pressure_normal_min
            high_type, low_type = AnomalyType.HIGH_PRESSURE, AnomalyType.LOW_PRESSURE
            unit = "PSI"

        if value > critical:
            return AnomalyResult(
                is_anomaly=True, anomaly_type=high_type, severity=AnomalySeverity.CRITICAL,
                description=f"Critical {sensor_type}: {value:.1f} {unit}",
                confidence=1.0,
                recommendations=[
                    f"Immediate {'valve closure' if sensor_type == 'temperature' else 'pressure relief'} required",
                    f"Emergency {'cooling protocol' if sensor_type == 'temperature' else 'depressurization'} required",
                    "Evacuate personnel from area"
                ]
            )
        elif value > alert:
            return AnomalyResult(
                is_anomaly=True, anomaly_type=high_type, severity=AnomalySeverity.HIGH,
                description=f"High {sensor_type} detected: {value:.1f} {unit}",
                confidence=0.95,
                recommendations=[
                    "Monitor closely for further increases",
                    f"Prepare for {'valve closure' if sensor_type == 'temperature' else 'pressure relief'}",
                    f"Check {'cooling systems' if sensor_type == 'temperature' else 'pressure regulators'}"
                ]
            )
        elif value > normal_max:
            return AnomalyResult(
                is_anomaly=True, anomaly_type=high_type, severity=AnomalySeverity.MEDIUM,
                description=f"{sensor_type.capitalize()} above normal: {value:.1f} {unit}",
                confidence=0.85,
                recommendations=[f"Monitor {sensor_type} trend", f"Check {'ventilation' if sensor_type == 'temperature' else 'flow rates'}"]
            )
        elif value < min_val:
            return AnomalyResult(
                is_anomaly=True, anomaly_type=low_type, severity=AnomalySeverity.HIGH,
                description=f"Very low {sensor_type}: {value:.1f} {unit}",
                confidence=0.95,
                recommendations=[f"Check for {'system shutdown' if sensor_type == 'temperature' else 'leaks'}", "Verify sensor readings"]
            )
        elif value < normal_min:
            return AnomalyResult(
                is_anomaly=True, anomaly_type=low_type, severity=AnomalySeverity.MEDIUM,
                description=f"{sensor_type.capitalize()} below normal: {value:.1f} {unit}",
                confidence=0.85,
                recommendations=["Monitor for further drops", f"Check {'heating systems' if sensor_type == 'temperature' else 'system integrity'}"]
            )

        return AnomalyResult(
            is_anomaly=False, anomaly_type=None, severity=None,
            description=f"{sensor_type.capitalize()} within normal range",
            confidence=0.9, recommendations=[]
        )
    
    def _check_combined_anomaly(self, temperature: float, pressure: float) -> AnomalyResult:
        temp_high = temperature > self.thresholds.temp_normal_max
        temp_critical = temperature > self.thresholds.temp_max
        pressure_high = pressure > self.thresholds.pressure_normal_max
        pressure_critical = pressure > self.thresholds.pressure_max

        temp_low = temperature < self.thresholds.temp_normal_min
        pressure_low = pressure < self.thresholds.pressure_normal_min

        if temp_critical and pressure_critical:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.COMBINED_HIGH,
                severity=AnomalySeverity.CRITICAL,
                description="Critical system overload - Temperature and Pressure",
                confidence=1.0,
                recommendations=[
                    "EMERGENCY SHUTDOWN REQUIRED",
                    "Activate all safety protocols",
                    "Evacuate immediately"
                ]
            )
        elif temp_high and pressure_high:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.COMBINED_HIGH,
                severity=AnomalySeverity.HIGH,
                description="Combined high temperature and pressure",
                confidence=0.95,
                recommendations=[
                    "System overheating detected",
                    "Reduce load immediately",
                    "Prepare for shutdown"
                ]
            )
        elif temp_low and pressure_low:
            if temperature < self.thresholds.temp_min and pressure < self.thresholds.pressure_min:
                return AnomalyResult(
                    is_anomaly=True,
                    anomaly_type=AnomalyType.COMBINED_LOW,
                    severity=AnomalySeverity.HIGH,
                    description="System shutdown detected",
                    confidence=0.95,
                    recommendations=[
                        "Verify system status",
                        "Check power supply",
                        "Restart procedures may be needed"
                    ]
                )
            else:
                return AnomalyResult(
                    is_anomaly=True,
                    anomaly_type=AnomalyType.COMBINED_LOW,
                    severity=AnomalySeverity.MEDIUM,
                    description="System underperformance",
                    confidence=0.85,
                    recommendations=["Check system efficiency", "Monitor performance"]
                )
        
        return AnomalyResult(
            is_anomaly=False,
            anomaly_type=None,
            severity=None,
            description="No combined anomaly detected",
            confidence=0.9,
            recommendations=[]
        )
    
    def _check_rapid_change(self, device_id: str, temperature: float, pressure: float) -> AnomalyResult:
        if device_id not in self.last_values:
            self.last_values[device_id] = {"temperature": temperature, "pressure": pressure, "timestamp": time.time()}
            return AnomalyResult(
                is_anomaly=False,
                anomaly_type=None,
                severity=None,
                description="First reading - no change detection",
                confidence=0.5,
                recommendations=[]
            )

        last = self.last_values[device_id]
        time_diff = time.time() - last["timestamp"]

        if time_diff < 60:
            temp_change = abs(temperature - last["temperature"])
            pressure_change = abs(pressure - last["pressure"])
            
            if temp_change > self.thresholds.rapid_change_temp:
                severity = AnomalySeverity.HIGH if temp_change > self.thresholds.rapid_change_temp * 1.5 else AnomalySeverity.MEDIUM
                return AnomalyResult(
                    is_anomaly=True,
                    anomaly_type=AnomalyType.RAPID_CHANGE,
                    severity=severity,
                    description=f"Rapid temperature change: {temp_change:.1f}°C in {time_diff:.0f}s",
                    confidence=0.9,
                    recommendations=["Investigate cause of rapid change", "Check sensor stability"]
                )
            
            if pressure_change > self.thresholds.rapid_change_pressure:
                severity = AnomalySeverity.HIGH if pressure_change > self.thresholds.rapid_change_pressure * 1.5 else AnomalySeverity.MEDIUM
                return AnomalyResult(
                    is_anomaly=True,
                    anomaly_type=AnomalyType.RAPID_CHANGE,
                    severity=severity,
                    description=f"Rapid pressure change: {pressure_change:.1f} PSI in {time_diff:.0f}s",
                    confidence=0.9,
                    recommendations=["Check for pressure surges", "Verify valve operations"]
                )
        
        self.last_values[device_id] = {"temperature": temperature, "pressure": pressure, "timestamp": time.time()}
        
        return AnomalyResult(
            is_anomaly=False,
            anomaly_type=None,
            severity=None,
            description="No rapid changes detected",
            confidence=0.85,
            recommendations=[]
        )
    
    def _check_sensor_failure(self, temperature: float, pressure: float) -> AnomalyResult:
        if temperature <= 0 or temperature >= 100:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.SENSOR_FAILURE,
                severity=AnomalySeverity.HIGH,
                description=f"Possible temperature sensor failure: {temperature}°C",
                confidence=0.95,
                recommendations=["Check sensor connection", "Calibrate or replace sensor"]
            )
        
        if pressure <= 0 or pressure >= 300:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.SENSOR_FAILURE,
                severity=AnomalySeverity.HIGH,
                description=f"Possible pressure sensor failure: {pressure} PSI",
                confidence=0.95,
                recommendations=["Check sensor connection", "Calibrate or replace sensor"]
            )
        
        return AnomalyResult(
            is_anomaly=False,
            anomaly_type=None,
            severity=None,
            description="Sensors operating normally",
            confidence=0.9,
            recommendations=[]
        )
    
    def _check_pattern_anomaly(self, device_id: str) -> AnomalyResult:
        if device_id not in self.history or len(self.history[device_id]) < 10:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_type=None,
                severity=None,
                description="Insufficient data for pattern analysis",
                confidence=0.3,
                recommendations=[]
            )

        # get last 10 readings
        recent_data = self.history[device_id][-10:]
        temps = [d["temperature"] for d in recent_data]
        pressures = [d["pressure"] for d in recent_data]

        temp_std = statistics.stdev(temps) if len(temps) > 1 else 0
        pressure_std = statistics.stdev(pressures) if len(pressures) > 1 else 0

        if temp_std > 5.0 or pressure_std > 10.0:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.PATTERN_ANOMALY,
                severity=AnomalySeverity.MEDIUM,
                description=f"Unstable readings detected (σ_T={temp_std:.1f}, σ_P={pressure_std:.1f})",
                confidence=0.75,
                recommendations=["Check for system instability", "Review control parameters"]
            )
        
        return AnomalyResult(
            is_anomaly=False,
            anomaly_type=None,
            severity=None,
            description="Normal pattern detected",
            confidence=0.8,
            recommendations=[]
        )
    
    def _update_history(self, device_id: str, temperature: float, pressure: float, timestamp: float):
        if device_id not in self.history:
            self.history[device_id] = []
        
        self.history[device_id].append({
            "temperature": temperature,
            "pressure": pressure,
            "timestamp": timestamp
        })
        
        if len(self.history[device_id]) > self.max_history_size:
            self.history[device_id] = self.history[device_id][-self.max_history_size:]
    
    def _update_anomaly_count(self, device_id: str):
        if device_id not in self.anomaly_counts:
            self.anomaly_counts[device_id] = {"count": 0, "last_reset": time.time()}
        
        self.anomaly_counts[device_id]["count"] += 1
        
        if time.time() - self.anomaly_counts[device_id]["last_reset"] > 3600:
            self.anomaly_counts[device_id] = {"count": 1, "last_reset": time.time()}
    
    def _severity_to_int(self, severity: Optional[AnomalySeverity]) -> int:
        if severity is None:
            return 0
        severity_map = {
            AnomalySeverity.LOW: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.HIGH: 3,
            AnomalySeverity.CRITICAL: 4
        }
        return severity_map.get(severity, 0)
    