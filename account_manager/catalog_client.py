import os
import requests
import logging
import time
import threading

from terminal_banner import print_banner

logger = logging.getLogger(__name__)


class CatalogClient:

    def __init__(self, catalog_url):
        self.catalog_url = catalog_url
        self.timeout = int(os.environ['HTTP_TIMEOUT'])
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
                timeout=self.timeout,
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

    def start_heartbeat(self, name, host, port, interval, health_endpoint="/health", description=""):
        def _loop():
            tick = 0
            while True:
                time.sleep(interval)
                tick += 1
                if self.register_service(name, host, port, health_endpoint, description):
                    print_banner(
                        "CATALOG HEARTBEAT",
                        [
                            f"service:  {name}",
                            f"address:  http://{host}:{port}",
                            f"catalog:  {self.catalog_url}",
                            f"id:       {self.service_id}",
                            f"tick:     {tick}",
                        ],
                        kind="info",
                    )
        threading.Thread(target=_loop, daemon=True, name="catalog-heartbeat").start()

    def delete_sectors_by_owner(self, user_id, internal_api_key):
        response = requests.delete(
            f"{self.catalog_url}/sectors/by-owner/{user_id}",
            headers={"X-Internal-API-Key": internal_api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def assign_user_to_sector(self, user_id, sector_id, internal_api_key, chat_id=None):
        if user_id in ("", None):
            payload_user_id = ""
        else:
            try:
                payload_user_id = int(user_id)
            except (ValueError, TypeError):
                payload_user_id = str(user_id)
        body = {"user_id": payload_user_id}
        if chat_id is not None:
            body["chat_id"] = "" if chat_id in ("", None) else str(chat_id)
        response = requests.put(
            f"{self.catalog_url}/sectors/{sector_id}/owner",
            json=body,
            headers={"X-Internal-API-Key": internal_api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
