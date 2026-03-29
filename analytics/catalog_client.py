import requests
import logging

logger = logging.getLogger(__name__)


class CatalogClient:
    def __init__(self, catalog_url="http://localhost:8081"):
        self.catalog_url = catalog_url
        self.service_id = None
        self.registered = False

    def register_service(self, host="localhost", port=8083):
        try:
            payload = {
                "name": "analytics", "host": host, "port": port,
                "health_endpoint": "/health",
                "description": "Analytics and anomaly detection service"
            }
            response = requests.post(f"{self.catalog_url}/services/register", json=payload, timeout=5)
            if response.status_code == 200:
                self.service_id = response.json().get("service_id")
                self.registered = True
                logger.info(f"Registered with Resource Catalog: {self.service_id}")
                return True
            logger.error(f"Failed to register: {response.status_code}")
        except Exception as e:
            logger.error(f"Error registering with Resource Catalog: {e}")
        return False

    def get_thresholds(self, sensor_type=None):
        try:
            params = {"type": sensor_type} if sensor_type else {}
            response = requests.get(f"{self.catalog_url}/config/thresholds", params=params, timeout=5)
            if response.status_code == 200:
                return response.json().get("thresholds", {})
            logger.error(f"Failed to fetch thresholds: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching thresholds: {e}")
        return {}

    def get_control_rules(self, rule_name=None):
        # rules for when to trigger actions
        try:
            params = {"name": rule_name} if rule_name else {}
            response = requests.get(f"{self.catalog_url}/config/rules", params=params, timeout=5)
            if response.status_code == 200:
                return response.json().get("control_rules", {})
            logger.error(f"Failed to fetch control rules: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching control rules: {e}")
        return {}

    def get_service_config(self, service_name="analytics"):
        try:
            response = requests.get(f"{self.catalog_url}/config/service/{service_name}", timeout=5)
            if response.status_code == 200:
                return response.json().get("config", {})
            logger.debug(f"No specific config for {service_name}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching service config: {e}")
        return {}

    def update_service_config(self, config):
        try:
            payload = {"service": "analytics", "config": config}
            response = requests.post(f"{self.catalog_url}/config/service", json=payload, timeout=5)
            if response.status_code == 200:
                logger.info("Service configuration updated in Resource Catalog")
                return True
            logger.error(f"Failed to update service config: {response.status_code}")
        except Exception as e:
            logger.error(f"Error updating service config: {e}")
        return False

    def get_pipeline_devices(self, pipeline_id):
        try:
            response = requests.get(f"{self.catalog_url}/devices/pipeline/{pipeline_id}", timeout=5)
            if response.status_code == 200:
                return response.json()
            logger.error(f"Failed to fetch pipeline devices: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching pipeline devices: {e}")
        return {}

    def get_all_pipelines(self):
        try:
            response = requests.get(f"{self.catalog_url}/devices/pipelines", timeout=5)
            if response.status_code == 200:
                return response.json().get("pipelines", {})
            logger.error(f"Failed to fetch pipelines: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching pipelines: {e}")
        return {}

    def update_bolt_data(self, bolt_id, temperature=None, pressure=None):
        try:
            payload = {}
            if temperature is not None:
                payload["temperature"] = temperature
            if pressure is not None:
                payload["pressure"] = pressure
            response = requests.put(f"{self.catalog_url}/devices/bolt/{bolt_id}", json=payload, timeout=5)
            if response.status_code == 200:
                return True
            logger.error(f"Failed to update bolt data: {response.status_code}")
        except Exception as e:
            logger.error(f"Error updating bolt data: {e}")
        return False

    def get_mqtt_config(self):
        try:
            response = requests.get(f"{self.catalog_url}/config/global", timeout=5)
            if response.status_code == 200:
                global_cfg = response.json().get("global_config", {})
                return {
                    "broker": global_cfg.get("mqtt_broker", "localhost"),
                    "port": global_cfg.get("mqtt_port", 1883)
                }
            logger.error(f"Failed to fetch MQTT config: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching MQTT config: {e}")
        return {}
