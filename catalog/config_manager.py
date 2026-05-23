import os
import logging

logger = logging.getLogger(__name__)

class ConfigurationManager:
    def __init__(self):
        self.configurations = {
            "global": {
                "mqtt_broker": os.environ["DEFAULT_MQTT_BROKER"],
                "mqtt_port": int(os.environ["DEFAULT_MQTT_PORT"]),
                "timeseries_db_url": os.environ["DEFAULT_TIMESERIES_DB_URL"],
                "publish_interval": int(os.environ["PUBLISH_INTERVAL"])
            },
            "thresholds": {
                "temperature": {
                    "min_normal": float(os.environ["TEMP_MIN_NORMAL"]),
                    "max_normal": float(os.environ["TEMP_MAX_NORMAL"]),
                    "alert": float(os.environ["TEMP_ALERT"]),
                    "critical": float(os.environ["TEMP_CRITICAL"])
                },
                "pressure": {
                    "min_normal": float(os.environ["PRESSURE_MIN_NORMAL"]),
                    "max_normal": float(os.environ["PRESSURE_MAX_NORMAL"]),
                    "alert": float(os.environ["PRESSURE_ALERT"]),
                    "critical": float(os.environ["PRESSURE_CRITICAL"])
                }
            },
            "control_rules": {
                "auto_shutdown": {
                    "enabled": os.environ["AUTO_SHUTDOWN_ENABLED"].lower() == "true",
                    "temperature_threshold": float(os.environ["TEMP_CRITICAL"]),
                    "pressure_threshold": float(os.environ["PRESSURE_CRITICAL"]),
                    "action": "close_valve"
                },
                "anomaly_response": {
                    "enabled": os.environ["ANOMALY_RESPONSE_ENABLED"].lower() == "true",
                    "consecutive_anomalies": int(os.environ["CONSECUTIVE_ANOMALIES_THRESHOLD"]),
                    "time_window": int(os.environ["ANOMALY_TIME_WINDOW"]),
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
