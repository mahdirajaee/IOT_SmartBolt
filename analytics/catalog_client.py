import os
import requests
import logging

logger = logging.getLogger(__name__)


class CatalogClient:
    def __init__(self, catalog_url="http://localhost:8081", account_manager_url=None):
        self.catalog_url = catalog_url
        self.account_manager_url = account_manager_url or os.getenv("ACCOUNT_MANAGER_URL", "http://localhost:8084")
        self.service_id = None
        self.registered = False

    def register_service(self, host="localhost", port=8083):
        try:
            from common_utils import CatalogClient as SharedClient
            client = SharedClient(self.catalog_url)
            if client.register_service(
                name="analytics", host=host, port=port,
                description="Analytics and anomaly detection service"
            ):
                self.service_id = client.service_id
                self.registered = True
                logger.info(f"Registered with Resource Catalog: {self.service_id}")
                return True
            logger.error("Failed to register with Resource Catalog")
        except Exception as e:
            logger.error(f"Error registering with Resource Catalog: {e}")
        return False

    def get_thresholds(self, sensor_type=None):
        try:
            params = {"type": sensor_type} if sensor_type else {}
            response = requests.get(f"{self.catalog_url}/config", params={**{"section": "thresholds"}, **params}, timeout=5)
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
            response = requests.get(f"{self.catalog_url}/config", params={**{"section": "rules"}, **params}, timeout=5)
            if response.status_code == 200:
                return response.json().get("control_rules", {})
            logger.error(f"Failed to fetch control rules: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching control rules: {e}")
        return {}


    def get_pipeline_devices(self, pipeline_id):
        try:
            response = requests.get(f"{self.catalog_url}/pipelines/{pipeline_id}", timeout=5)
            if response.status_code == 200:
                return response.json()
            logger.error(f"Failed to fetch pipeline devices: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching pipeline devices: {e}")
        return {}

    def get_all_pipelines(self):
        try:
            response = requests.get(f"{self.catalog_url}/pipelines", timeout=5)
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
            response = requests.put(f"{self.catalog_url}/bolts/{bolt_id}", json=payload, timeout=5)
            if response.status_code == 200:
                return True
            logger.error(f"Failed to update bolt data: {response.status_code}")
        except Exception as e:
            logger.error(f"Error updating bolt data: {e}")
        return False

    def get_mqtt_config(self):
        try:
            response = requests.get(f"{self.catalog_url}/config", params={"section": "global"}, timeout=5)
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

    def get_chat_ids_for_sector(self, sector_id):
        try:
            response = requests.get(f"{self.catalog_url}/users", timeout=5)
            if response.status_code != 200:
                logger.error(f"Failed to fetch users: {response.status_code}")
                return []
            users = response.json().get("users", [])
            seen = set()
            chat_ids = []
            for user in users:
                user_sectors = [s.get("sectorID") for s in user.get("sectors", [])]
                if sector_id in user_sectors:
                    chat_id = user.get("chatID")
                    if chat_id and chat_id not in seen:
                        seen.add(chat_id)
                        chat_ids.append(chat_id)
            return chat_ids
        except Exception as e:
            logger.error(f"Error fetching chat_ids for sector {sector_id}: {e}")
            return []
