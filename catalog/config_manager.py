import os
import logging

logger = logging.getLogger(__name__)

class ConfigurationManager:
    def __init__(self):
        self.configurations = {
            "global": {
                "mqtt_broker": os.getenv("DEFAULT_MQTT_BROKER", "localhost"),
                "mqtt_port": int(os.getenv("DEFAULT_MQTT_PORT", 1883)),
                "timeseries_db_url": os.getenv("DEFAULT_TIMESERIES_DB_URL", "http://localhost:8082"),
                "publish_interval": int(os.getenv("PUBLISH_INTERVAL", 5))
            },
            "thresholds": {
                "temperature": {
                    "min_normal": float(os.getenv("TEMP_MIN_NORMAL", 20.0)),
                    "max_normal": float(os.getenv("TEMP_MAX_NORMAL", 40.0)),
                    "alert": float(os.getenv("TEMP_ALERT", 45.0)),
                    "critical": float(os.getenv("TEMP_CRITICAL", 60.0))
                },
                "pressure": {
                    "min_normal": float(os.getenv("PRESSURE_MIN_NORMAL", 90.0)),
                    "max_normal": float(os.getenv("PRESSURE_MAX_NORMAL", 110.0)),
                    "alert": float(os.getenv("PRESSURE_ALERT", 120.0)),
                    "critical": float(os.getenv("PRESSURE_CRITICAL", 150.0))
                }
            },
            "control_rules": {
                "auto_shutdown": {
                    "enabled": os.getenv("AUTO_SHUTDOWN_ENABLED", "true").lower() == "true",
                    "temperature_threshold": float(os.getenv("TEMP_CRITICAL", 60.0)),
                    "pressure_threshold": float(os.getenv("PRESSURE_CRITICAL", 150.0)),
                    "action": "close_valve"
                },
                "anomaly_response": {
                    "enabled": os.getenv("ANOMALY_RESPONSE_ENABLED", "true").lower() == "true",
                    "consecutive_anomalies": int(os.getenv("CONSECUTIVE_ANOMALIES_THRESHOLD", 3)),
                    "time_window": int(os.getenv("ANOMALY_TIME_WINDOW", 60)),
                    "action": "alert"
                }
            }
        }

    def get_global_config(self):
        return self.configurations["global"]

    def get_thresholds(self, sensor_type=None):
        if sensor_type:
            return self.configurations["thresholds"].get(sensor_type, {})
        return self.configurations["thresholds"]

    def get_control_rules(self, rule_name=None):
        if rule_name:
            return self.configurations["control_rules"].get(rule_name, {})
        return self.configurations["control_rules"]
