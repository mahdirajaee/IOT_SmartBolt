import random
import time
import logging
import os
import math
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SensorLimits:
    temp_min: float = 20.0
    temp_max: float = 50.0
    pressure_min: float = 80.0
    pressure_max: float = 120.0

@dataclass
class SensorConfig:
    normal_noise_std: float = float(os.getenv("NORMAL_NOISE_STD", "0.5"))
    drift_rate: float = float(os.getenv("DRIFT_RATE", "0.001"))
    temp_alert_threshold: float = float(os.getenv("TEMP_ALERT_THRESHOLD", "45.0"))
    pressure_alert_threshold: float = float(os.getenv("PRESSURE_ALERT_THRESHOLD", "115.0"))
    smoothing_factor: float = float(os.getenv("SMOOTHING_FACTOR", "0.5"))
    wave_duration: float = float(os.getenv("WAVE_DURATION", "30.0"))
    wave_cycle_min: float = float(os.getenv("WAVE_CYCLE_MIN", "30.0"))
    wave_cycle_max: float = float(os.getenv("WAVE_CYCLE_MAX", "60.0"))
    temp_wave_amplitude: float = float(os.getenv("TEMP_WAVE_AMPLITUDE", "30.0"))
    pressure_wave_amplitude: float = float(os.getenv("PRESSURE_WAVE_AMPLITUDE", "25.0"))
    critical_spike_probability: float = float(os.getenv("CRITICAL_SPIKE_PROBABILITY", "0.05"))
    critical_spike_temp_min: float = float(os.getenv("CRITICAL_SPIKE_TEMP_MIN", "50.0"))
    critical_spike_temp_max: float = float(os.getenv("CRITICAL_SPIKE_TEMP_MAX", "65.0"))
    critical_spike_pressure_min: float = float(os.getenv("CRITICAL_SPIKE_PRESSURE_MIN", "118.0"))
    critical_spike_pressure_max: float = float(os.getenv("CRITICAL_SPIKE_PRESSURE_MAX", "140.0"))

class Bolt:
    # see north

    def __init__(self, bolt_id, limits=None):
        self.bolt_id = bolt_id
        self.limits = limits or SensorLimits()
        self.config = SensorConfig()

        self.temp_target = self.limits.temp_min + (self.limits.temp_max - self.limits.temp_min) * 0.4
        self.pressure_target = self.limits.pressure_min + (self.limits.pressure_max - self.limits.pressure_min) * 0.4

        self.temperature = random.gauss(self.temp_target, self.config.normal_noise_std)
        self.pressure = random.gauss(self.pressure_target, self.config.normal_noise_std)

        self.temp_smooth = self.temperature
        self.pressure_smooth = self.pressure

        self.wave_start_time = 0.0
        self.next_wave_time = time.time() + random.uniform(
            self.config.wave_cycle_min, self.config.wave_cycle_max
        )
        self.in_wave = False
        self.wave_temp_enabled = True
        self.wave_pressure_enabled = False

        self.health = 100.0
        self.last_update = time.time()
        self.temp_drift = 0.0
        self.pressure_drift = 0.0
        self.critical_spike_active = False

    def _check_critical_spike(self) -> tuple:
        if random.random() < self.config.critical_spike_probability:
            temp_spike = random.uniform(
                self.config.critical_spike_temp_min,
                self.config.critical_spike_temp_max
            )
            pressure_spike = random.uniform(
                self.config.critical_spike_pressure_min,
                self.config.critical_spike_pressure_max
            )
            return True, temp_spike, pressure_spike
        return False, 0.0, 0.0

    def generate_data(self, valve_position=0.0):
        current_time = time.time()
        time_delta = current_time - self.last_update

        if not self.in_wave and current_time >= self.next_wave_time:
            self._start_wave()

        return self._generate_realistic_data(valve_position, time_delta)

    def _start_wave(self):
        self.in_wave = True
        self.wave_start_time = time.time()
        self.wave_temp_enabled = random.random() < 0.7
        self.wave_pressure_enabled = random.random() < 0.4
        if not self.wave_temp_enabled and not self.wave_pressure_enabled:
            self.wave_temp_enabled = True

    def _gaussian_deviation(self, t):
        duration = self.config.wave_duration
        center = duration / 2
        sigma = duration / 6
        return math.exp(-((t - center) ** 2) / (2 * sigma ** 2))

    def _generate_realistic_data(self, valve_position, time_delta):
        current_time = time.time()
        temp_noise = random.gauss(0, self.config.normal_noise_std)
        pressure_noise = random.gauss(0, self.config.normal_noise_std)

        self.temp_drift += random.gauss(0, self.config.drift_rate)
        self.pressure_drift += random.gauss(0, self.config.drift_rate)

        wave_temp_effect = 0.0
        wave_pressure_effect = 0.0

        if self.in_wave:
            wave_age = current_time - self.wave_start_time

            if wave_age <= self.config.wave_duration:
                deviation = self._gaussian_deviation(wave_age)
                if self.wave_temp_enabled:
                    wave_temp_effect = deviation * self.config.temp_wave_amplitude
                if self.wave_pressure_enabled:
                    wave_pressure_effect = deviation * self.config.pressure_wave_amplitude
            else:
                self.in_wave = False
                self.next_wave_time = current_time + random.uniform(
                    self.config.wave_cycle_min, self.config.wave_cycle_max
                )

        raw_temp = self.temp_target + temp_noise + self.temp_drift + wave_temp_effect
        raw_pressure = self.pressure_target + pressure_noise + self.pressure_drift + wave_pressure_effect

        self.temp_smooth = (self.config.smoothing_factor * self.temp_smooth +
                           (1 - self.config.smoothing_factor) * raw_temp)
        self.pressure_smooth = (self.config.smoothing_factor * self.pressure_smooth +
                               (1 - self.config.smoothing_factor) * raw_pressure)

        self.temperature = self.temp_smooth
        self.pressure = self.pressure_smooth

        spike_active, spike_temp, spike_pressure = self._check_critical_spike()
        if spike_active:
            self.critical_spike_active = True
            self.temperature = spike_temp
            self.pressure = spike_pressure
        else:
            self.critical_spike_active = False
            self.temperature = max(self.limits.temp_min, min(self.limits.temp_max, self.temperature))
            self.pressure = max(self.limits.pressure_min, min(self.limits.pressure_max, self.pressure))

        self.health = max(0, self.health - random.uniform(0, 0.001))
        self.last_update = current_time

        return {
            "temperature": round(self.temperature, 2),
            "pressure": round(self.pressure, 2),
            "health": round(self.health, 1),
            "anomaly_active": self.in_wave,
            "critical_spike": self.critical_spike_active,
            "valve_position": valve_position
        }


    def reset(self):
        self.temperature = random.gauss(self.temp_target, self.config.normal_noise_std)
        self.pressure = random.gauss(self.pressure_target, self.config.normal_noise_std)
        self.temp_smooth = self.temperature
        self.pressure_smooth = self.pressure
        self.health = 100.0
        self.temp_drift = 0.0
        self.pressure_drift = 0.0
        self.in_wave = False
        self.wave_start_time = 0.0
        self.next_wave_time = time.time() + random.uniform(
            self.config.wave_cycle_min, self.config.wave_cycle_max
        )
        self.last_update = time.time()

class Valve:

    VALID_STATES = ["open", "closed", "error"]

    def __init__(self, valve_id, initial_state="closed"):
        self.valve_id = valve_id
        self.state = initial_state if initial_state in self.VALID_STATES else "closed"
        self.position = 0.0 if self.state == "closed" else 100.0
        self.health = 100.0
        self.last_command_time = time.time()
        self.command_count = 0
        self.error_count = 0

    def set_state(self, new_state: str) -> bool:
        if new_state not in ["open", "closed"]:
            logger.error(f"Invalid valve state requested: {new_state}")
            return False

        if self.state == new_state:
            logger.debug(f"Valve {self.valve_id} already in state {new_state}")
            return True

        self.last_command_time = time.time()
        self.command_count += 1

        if random.random() < 0.02:
            self.state = "error"
            self.error_count += 1
            logger.error(f"Valve {self.valve_id} failed to change to {new_state}")
            return False

        self.state = new_state
        self.position = 100.0 if new_state == "open" else 0.0
        logger.info(f"Valve {self.valve_id} set to {new_state}")
        return True

    def update(self) -> Dict[str, Any]:
        self.health = max(0, self.health - 0.001 - (0.01 * self.error_count))
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        return {
            "valve_id": self.valve_id,
            "state": self.state,
            "position": round(self.position, 1),
            "health": round(self.health, 1),
            "command_count": self.command_count,
            "error_count": self.error_count
        }

    def reset(self):
        self.state = "closed"
        self.position = 0.0
        self.health = 100.0
        self.last_command_time = time.time()
        self.command_count = 0
        self.error_count = 0

class Pipeline:

    def __init__(self, pid):
        self.pipeline_id = pid
        self.bolts: Dict[str, Bolt] = {}
        self.valves: Dict[str, Valve] = {}
        self.status = "active"
        self.created_at = time.time()
        self.data_points_generated = 0

    def add_bolt(self, bolt_id: str, limits: Optional[SensorLimits] = None) -> Bolt:
        bolt = Bolt(bolt_id, limits)
        self.bolts[bolt_id] = bolt
        logger.debug(f"Added bolt {bolt_id} to pipeline {self.pipeline_id}")
        return bolt

    def add_valve(self, valve_id: str, initial_state: str = "closed") -> Valve:
        valve = Valve(valve_id, initial_state)
        self.valves[valve_id] = valve
        logger.debug(f"Added valve {valve_id} to pipeline {self.pipeline_id}")
        return valve

    def generate_data(self) -> Dict[str, Any]:
        bolt_data = {}
        valve_status = {}

        valve_positions = {}
        for valve_id, valve in self.valves.items():
            valve_positions[valve_id] = valve.position

        avg_valve_position = sum(valve_positions.values()) / len(valve_positions) if valve_positions else 0.0

        avg_temp = 0.0
        avg_pressure = 0.0
        bolt_count = len(self.bolts)

        for bolt_id, bolt in self.bolts.items():
            bolt_data[bolt_id] = bolt.generate_data(avg_valve_position)
            avg_temp += bolt_data[bolt_id]["temperature"]
            avg_pressure += bolt_data[bolt_id]["pressure"]

        if bolt_count > 0:
            avg_temp /= bolt_count
            avg_pressure /= bolt_count

        for valve_id, valve in self.valves.items():
            valve_status[valve_id] = valve.update()

        active_valves = sum(1 for v in self.valves.values() if v.state == "open")

        self.data_points_generated += 1

        return {
            "timestamp": time.time(),
            "pipeline_id": self.pipeline_id,
            "sector_id": os.getenv("SECTOR_ID", "sector-unknown"),
            "status": "active",
            "bolt_data": bolt_data,
            "valve_status": valve_status,
            "system_status": {
                "avg_temperature": round(avg_temp, 2),
                "avg_pressure": round(avg_pressure, 2),
                "active_valves": active_valves,
                "valve_effectiveness": round(avg_valve_position, 1)
            },
            "metadata": {
                "data_points": self.data_points_generated,
                "uptime": time.time() - self.created_at
            }
        }

    def set_valve_state(self, valve_id: str, state: str) -> bool:
        if valve_id in self.valves:
            return self.valves[valve_id].set_state(state)
        logger.error(f"Valve {valve_id} not found in pipeline {self.pipeline_id}")
        return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status,
            "bolt_count": len(self.bolts),
            "valve_count": len(self.valves),
            "data_points": self.data_points_generated,
            "uptime": time.time() - self.created_at,
            "bolts": list(self.bolts.keys()),
            "valves": list(self.valves.keys())
        }

    def reset(self):
        for bolt in self.bolts.values():
            bolt.reset()
        for valve in self.valves.values():
            valve.reset()
        self.data_points_generated = 0
        logger.info(f"Pipeline {self.pipeline_id} reset")
