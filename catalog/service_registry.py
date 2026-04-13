import time
import requests
import threading
import logging

logger = logging.getLogger(__name__)

class ServiceRegistry:
    # keeps track of which services are running
    def __init__(self, device_manager=None):
        self.services = {}
        self.health_check_interval = 30  # health check every 30s - is this too often?
        self.health_check_thread = None
        self.running = False
        self.device_manager = device_manager

    def set_device_manager(self, device_manager):
        self.device_manager = device_manager

    def register_service(self, service_name, host, port, health_endpoint="/health", description=""):
        service_id = f"{service_name}_{host}_{port}"
        rest_endpoint = f"http://{host}:{port}"

        self.services[service_id] = {
            "name": service_name,
            "host": host,
            "port": port,
            "health_endpoint": health_endpoint,
            "description": description,
            "status": "unknown",
            "last_heartbeat": time.time(),
            "registered_at": time.time(),
            "health_check_url": f"http://{host}:{port}{health_endpoint}",
            "consecutive_failures": 0
        }

        if self.device_manager:
            self.device_manager.update_service_in_catalog(service_name, rest_endpoint)

        #print(f"registered {service_name}")  # debug
        logger.info(f"Service registered: {service_name} at {host}:{port}")
        return service_id

    def unregister_service(self, service_id):
        if service_id in self.services:
            service = self.services.pop(service_id)
            logger.info(f"Service unregistered: {service['name']} at {service['host']}:{service['port']}")
            return True
        return False

    def get_service(self, service_name):
        for service_id, service in self.services.items():
            if service["name"] == service_name and service["status"] == "healthy":
                return service
        return None

    def get_all_services(self):
        return self.services

    def get_services_by_name(self, service_name):
        return {
            sid: service for sid, service in self.services.items()
            if service["name"] == service_name
        }

    def update_service_status(self, service_id, status):
        if service_id in self.services:
            self.services[service_id]["status"] = status
            self.services[service_id]["last_heartbeat"] = time.time()

    def check_service_health(self, service_id):
        if service_id not in self.services:
            return False

        service = self.services[service_id]
        try:
            response = requests.get(service["health_check_url"], timeout=5)
            if response.status_code == 200:
                self.update_service_status(service_id, "healthy")
                service["consecutive_failures"] = 0
                return True
            else:
                self.update_service_status(service_id, "unhealthy")
                service["consecutive_failures"] = service.get("consecutive_failures", 0) + 1
                return False
        except Exception as e:
            logger.warning(f"Health check failed for {service['name']}: {e}")
            self.update_service_status(service_id, "unreachable")
            service["consecutive_failures"] = service.get("consecutive_failures", 0) + 1
            return False

    def start_health_checks(self):
        self.running = True
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_thread.start()
        logger.info("Health check monitoring started")

    def stop_health_checks(self):
        self.running = False
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5)
        logger.info("Health check monitoring stopped")

    def _health_check_loop(self):
        STALE_THRESHOLD = 10
        while self.running:
            for service_id in list(self.services.keys()):
                if not self.running:
                    break
                self.check_service_health(service_id)
                svc = self.services.get(service_id, {})
                if svc.get("consecutive_failures", 0) >= STALE_THRESHOLD:
                    logger.info(f"Pruning stale service: {svc.get('name')} (id={service_id})")
                    self.services.pop(service_id, None)
            time.sleep(self.health_check_interval)
