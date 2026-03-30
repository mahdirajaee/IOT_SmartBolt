import json
import os
import time
import logging

logger = logging.getLogger(__name__)

class ConfigurationManager:
    def __init__(self):
        self.configurations = {
            "global": {
                "mqtt_broker": os.getenv("DEFAULT_MQTT_BROKER", "localhost"),
                "mqtt_port": int(os.getenv("DEFAULT_MQTT_PORT", 1883)),
                "influxdb_url": os.getenv("DEFAULT_INFLUXDB_URL", "http://localhost:8082"),
                "influxdb_org": os.getenv("DEFAULT_INFLUXDB_ORG", "iot_monitoring"),
                "influxdb_bucket": os.getenv("DEFAULT_INFLUXDB_BUCKET", "iot_data")
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
            },
            "services": {}
        }
        
    def set_service_config(self, service_name, config):
        #print(f"config for {service_name}")  # debug
        self.configurations["services"][service_name] = {
            "config": config,
            "updated_at": time.time()
        }
        logger.info(f"Configuration set for service: {service_name}")
        return True
    
    def get_service_config(self, service_name):
        if service_name in self.configurations["services"]:
            return self.configurations["services"][service_name]["config"]
        return {}
    
    def update_service_config(self, service_name, updates):
        if service_name not in self.configurations["services"]:
            self.configurations["services"][service_name] = {"config": {}, "updated_at": time.time()}
        
        self.configurations["services"][service_name]["config"].update(updates)
        self.configurations["services"][service_name]["updated_at"] = time.time()
        logger.info(f"Configuration updated for service: {service_name}")
        return True
    
    def get_global_config(self):
        return self.configurations["global"]
    
    def update_global_config(self, updates):
        self.configurations["global"].update(updates)
        logger.info("Global configuration updated")
        return True
    
    def get_thresholds(self, sensor_type=None):
        if sensor_type:
            return self.configurations["thresholds"].get(sensor_type, {})
        return self.configurations["thresholds"]
    
    def update_thresholds(self, sensor_type, thresholds):
        if sensor_type in self.configurations["thresholds"]:
            self.configurations["thresholds"][sensor_type].update(thresholds)
            logger.info(f"Thresholds updated for {sensor_type}")
            return True
        return False
    
    def get_control_rules(self, rule_name=None):
        if rule_name:
            return self.configurations["control_rules"].get(rule_name, {})
        return self.configurations["control_rules"]
    
    def update_control_rule(self, rule_name, rule_config):
        self.configurations["control_rules"][rule_name] = rule_config
        logger.info(f"Control rule updated: {rule_name}")
        return True
    
    def get_all_configurations(self):
        return self.configurations
    
    def export_config(self):
        return json.dumps(self.configurations, indent=2)
    
    def import_config(self, config_json):
        try:
            imported_config = json.loads(config_json)
            self.configurations.update(imported_config)
            logger.info("Configuration imported successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            return False
    
    def get_mqtt_config(self):
        return {
            "broker": self.configurations["global"].get("mqtt_broker", "localhost"),
            "port": self.configurations["global"].get("mqtt_port", 1883)
        }
    
    def get_influxdb_config(self):
        return {
            "url": self.configurations["global"].get("influxdb_url", "http://localhost:8082"),
            "org": self.configurations["global"].get("influxdb_org", "iot_monitoring"),
            "bucket": self.configurations["global"].get("influxdb_bucket", "iot_data")
        }