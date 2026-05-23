import requests
import logging

logger = logging.getLogger(__name__)


class CatalogClient:

    def __init__(self, catalog_url="http://localhost:8081"):
        self.catalog_url = catalog_url
        self.service_id = None
        self.registered = False

    def register_service(self, name, host, port, health_endpoint="/health", description=""):
        try:
            payload = {
                "name": name,
                "host": host,
                "port": port,
                "health_endpoint": health_endpoint,
                "description": description,
            }

            response = requests.post(
                f"{self.catalog_url}/services/register",
                json=payload,
                timeout=5,
            )

            if response.status_code == 200:
                result = response.json()
                self.service_id = result.get("service_id")
                self.registered = True
                logger.info(f"Successfully registered '{name}' with Catalog: {self.service_id}")
                return True

            logger.error(f"Failed to register '{name}' with Catalog: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Error registering '{name}' with Catalog: {e}")
            return False
