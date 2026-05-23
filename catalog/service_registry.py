import os
import time
import requests
import threading
import logging
from terminal_banner import print_banner

logger = logging.getLogger(__name__)

class ServiceRegistry:
    # keeps track of which services are running
    def __init__(self, device_manager=None):
        self.services = {}
        self.lock = threading.RLock()
        self.health_check_interval = int(os.environ['HEALTH_CHECK_INTERVAL'])
        self.http_timeout = int(os.environ['HTTP_TIMEOUT'])
        self.stale_threshold = int(os.environ['STALE_THRESHOLD'])
        self.health_check_thread = None
        self.running = False
        self.device_manager = device_manager

    def register_service(self, service_name, host, port, health_endpoint="/health", description=""):
        service_id = f"{service_name}_{host}_{port}"
        rest_endpoint = f"http://{host}:{port}"
        now = time.time()

        with self.lock:
            existing = service_id in self.services
            if existing:
                self.services[service_id]["last_heartbeat"] = now
            else:
                self.services[service_id] = {
                    "name": service_name,
                    "service_id": service_id,
                    "host": host,
                    "port": port,
                    "health_endpoint": health_endpoint,
                    "description": description,
                    "status": "unknown",
                    "last_heartbeat": now,
                    "registered_at": now,
                    "health_check_url": f"http://{host}:{port}{health_endpoint}",
                    "consecutive_failures": 0
                }

        if existing:
            return service_id

        if self.device_manager:
            self.device_manager.update_service_in_catalog(service_name, rest_endpoint)

        logger.info(f"Service registered: {service_name} at {host}:{port}")
        print_banner(
            "SERVICE REGISTERED",
            [f"{service_name} @ {host}:{port}", f"id: {service_id}"],
            kind="success",
        )
        return service_id

    def remove_service(self, service_id):
        with self.lock:
            resolved_id = service_id
            if resolved_id not in self.services:
                resolved_id = next(
                    (sid for sid, service in self.services.items() if service.get("name") == service_id),
                    None
                )

            if not resolved_id or resolved_id not in self.services:
                return None

            removed = self.services.pop(resolved_id)

        if self.device_manager:
            self.device_manager.remove_service_from_catalog(removed["name"])

        logger.info(f"Service removed: {removed['name']} (id={resolved_id})")
        return removed

    def get_all_services(self):
        with self.lock:
            return {service_id: service.copy() for service_id, service in self.services.items()}

    def update_service_status(self, service_id, status):
        with self.lock:
            if service_id in self.services:
                self.services[service_id]["status"] = status
                self.services[service_id]["last_heartbeat"] = time.time()

    def check_service_health(self, service_id):
        with self.lock:
            if service_id not in self.services:
                return False
            service = self.services[service_id].copy()

        try:
            response = requests.get(service["health_check_url"], timeout=self.http_timeout)
            if response.status_code == 200:
                with self.lock:
                    if service_id in self.services:
                        self.services[service_id]["status"] = "healthy"
                        self.services[service_id]["last_heartbeat"] = time.time()
                        self.services[service_id]["consecutive_failures"] = 0
                return True
            else:
                with self.lock:
                    if service_id in self.services:
                        self.services[service_id]["status"] = "unhealthy"
                        self.services[service_id]["last_heartbeat"] = time.time()
                        self.services[service_id]["consecutive_failures"] = self.services[service_id].get("consecutive_failures", 0) + 1
                return False
        except Exception as e:
            logger.warning(f"Health check failed for {service['name']}: {e}")
            with self.lock:
                if service_id in self.services:
                    self.services[service_id]["status"] = "unreachable"
                    self.services[service_id]["last_heartbeat"] = time.time()
                    self.services[service_id]["consecutive_failures"] = self.services[service_id].get("consecutive_failures", 0) + 1
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
        while self.running:
            with self.lock:
                service_ids = list(self.services.keys())

            for service_id in service_ids:
                if not self.running:
                    break
                self.check_service_health(service_id)

                with self.lock:
                    svc = self.services.get(service_id, {})
                    if svc.get("consecutive_failures", 0) >= self.stale_threshold:
                        logger.info(f"Pruning stale service: {svc.get('name')} (id={service_id})")
                        print_banner(
                            "SERVICE PRUNED",
                            [
                                f"{svc.get('name', '?')} @ {svc.get('host', '?')}:{svc.get('port', '?')}",
                                f"reason: {self.stale_threshold} consecutive health-check failures",
                            ],
                            kind="warning",
                        )
                        self.remove_service(service_id)
            time.sleep(self.health_check_interval)
