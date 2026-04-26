import os
import requests
import logging
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from internal_auth import resolve_internal_api_key

logger = logging.getLogger(__name__)


class CatalogClient:
    def __init__(self, catalog_url="http://localhost:8081", account_manager_url=None):
        self.catalog_url = catalog_url
        self.account_manager_url = account_manager_url or os.getenv("ACCOUNT_MANAGER_URL", "http://localhost:8084")
        self.internal_api_key = resolve_internal_api_key("analytics")
        self.service_id = None
        self.registered = False

    def _internal_auth_headers(self):
        return {"X-Internal-API-Key": self.internal_api_key}

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
                logger.info(f"Registered with Catalog: {self.service_id}")
                return True
            logger.error("Failed to register with Catalog")
        except Exception as e:
            logger.error(f"Error registering with Catalog: {e}")
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

    def get_chat_ids_for_sector(self, sector_id):
        try:
            response = requests.get(
                f"{self.account_manager_url}/internal/chat-ids",
                params={"sector_id": sector_id},
                headers=self._internal_auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("chat_ids", [])
            logger.error(f"Failed to fetch chat_ids: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching chat_ids for sector {sector_id}: {e}")
        return []
