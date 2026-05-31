import cherrypy
import os
import json
import logging
import time
import signal
import sys
import subprocess
import platform
import threading
from dotenv import load_dotenv
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MyMQTT import MyMQTT

import requests
from service_log import print_banner

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.environ["LOG_LEVEL"]),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CatalogClient:
    def __init__(self, catalog_url):
        self.catalog_url = catalog_url
        self.timeout = int(os.environ["HTTP_TIMEOUT"])
        self.service_id = None
        self.registered = False

    def register_service(self, name, host, port, health_endpoint="/health", description=""):
        try:
            response = requests.post(
                f"{self.catalog_url}/services/register",
                json={
                    "name": name,
                    "host": host,
                    "port": port,
                    "health_endpoint": health_endpoint,
                    "description": description,
                },
                timeout=self.timeout,
            )
            if response.status_code == 200:
                self.service_id = response.json().get("service_id")
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
                            f"svc:  {name}",
                            f"addr: http://{host}:{port}",
                            f"cat:  {self.catalog_url}",
                            f"id:   {self.service_id}",
                            f"tick: {tick}",
                        ],
                        kind="info",
                    )
        threading.Thread(target=_loop, daemon=True, name="catalog-heartbeat").start()


class BrokerMonitor:
    def __init__(self, broker, port):
        self.broker = broker
        self.port = port
        self.client_id = os.environ["MQTT_CLIENT_ID"]
        self.start_wait = int(os.environ["MQTT_START_WAIT"])
        self.mqtt = MyMQTT(self.client_id, self.broker, self.port, self)
        self.connected = False
        self.stats = {
            "messages_monitored": 0,
            "start_time": time.time(),
            "topics_seen": {}
        }

    def notify(self, topic, payload):
        self.stats["messages_monitored"] += 1
        base = topic.split("/")[0]
        self.stats["topics_seen"][base] = self.stats["topics_seen"].get(base, 0) + 1

    def start(self):
        try:
            self.mqtt.start()
            time.sleep(self.start_wait)
            self.connected = True

            self.mqtt.mySubscribe("sectors/+/pipelines/+/measurements")
            self.mqtt.mySubscribe("sectors/+/pipelines/+/alerts/+")
            self.mqtt.mySubscribe("sectors/+/pipelines/+/commands/valves")
            self.mqtt.mySubscribe("telegram/commands/+")
            self.mqtt.mySubscribe("alerts/anomalies/+")

            logger.info("Broker monitor started - tracking all MQTT traffic")
            print_banner(
                "BROKER MONITOR STARTED",
                [
                    f"client: {self.client_id}",
                    f"subs:   5 topics",
                    f"broker: {self.broker}:{self.port}",
                ],
                kind="info",
            )
            return True
        except Exception as e:
            logger.error(f"Monitor connection error: {e}")
            return False

    def stop(self):
        self.mqtt.stop()
        self.connected = False

    def get_stats(self):
        uptime = time.time() - self.stats["start_time"]
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "messages_per_minute": (self.stats["messages_monitored"] / uptime) * 60 if uptime > 0 else 0,
            "connected": self.connected
        }


class MosquittoManager:
    def __init__(self):
        self.system = platform.system()
        self.broker_host = os.environ["MQTT_BROKER"]
        self.broker_port = int(os.environ["MQTT_PORT"])
        self.socket_timeout = int(os.environ["MOSQUITTO_SOCKET_TIMEOUT"])
        self.start_wait = int(os.environ["MOSQUITTO_START_WAIT"])

    def is_running(self) -> bool:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.socket_timeout)
            result = sock.connect_ex((self.broker_host, self.broker_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def start(self) -> bool:
        if self.is_running():
            logger.info(f"Mosquitto already running on {self.broker_host}:{self.broker_port}")
            print_banner(
                "MOSQUITTO STATE",
                [
                    f"state: already-running",
                    f"host:  {self.broker_host}",
                    f"port:  {self.broker_port}",
                ],
                kind="success",
            )
            return True

        try:
            if self.system == "Darwin":
                subprocess.run(["brew", "services", "start", "mosquitto"], check=True)
            elif self.system == "Linux":
                subprocess.run(["sudo", "systemctl", "start", "mosquitto"], check=True)
            else:
                subprocess.Popen(["mosquitto", "-d"])

            time.sleep(self.start_wait)
            running = self.is_running()
            if running:
                logger.info("Mosquitto started successfully")
                print_banner(
                    "MOSQUITTO STATE",
                    [
                        f"state: started",
                        f"host:  {self.broker_host}",
                        f"port:  {self.broker_port}",
                    ],
                    kind="success",
                )
            else:
                logger.error("Mosquitto failed to start")
                print_banner(
                    "MOSQUITTO STATE",
                    [
                        f"state: failed",
                        f"host:  {self.broker_host}",
                        f"port:  {self.broker_port}",
                        f"why:   service did not bind after start",
                    ],
                    kind="danger",
                )
            return running
        except Exception as e:
            logger.error(f"Error starting Mosquitto: {e}")
            print_banner(
                "MOSQUITTO STATE",
                [
                    f"state: failed",
                    f"host:  {self.broker_host}",
                    f"port:  {self.broker_port}",
                    f"why:   {e}",
                ],
                kind="danger",
            )
            return False

    def stop(self) -> bool:
        try:
            if self.system == "Darwin":
                subprocess.run(["brew", "services", "stop", "mosquitto"], check=True)
            elif self.system == "Linux":
                subprocess.run(["sudo", "systemctl", "stop", "mosquitto"], check=True)
            logger.info("Mosquitto stopped")
            return True
        except Exception as e:
            logger.error(f"Error stopping Mosquitto: {e}")
            return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "broker": self.broker_host,
            "port": self.broker_port,
            "running": self.is_running(),
            "platform": self.system
        }


class MessageBrokerWebService(object):
    exposed = True

    def __init__(self):
        self.mosquitto = MosquittoManager()
        self.broker_host = os.environ["MQTT_BROKER"]
        self.broker_port = int(os.environ["MQTT_PORT"])

        if not self.mosquitto.is_running():
            logger.warning("Mosquitto is not running, attempting to start...")
        self.mosquitto.start()

        self.monitor = BrokerMonitor(self.broker_host, self.broker_port)
        self.monitor.start()

        self.start_time = time.time()

    def json_response(self, data):
        return json.dumps(data).encode('utf-8')

    def GET(self, *path, **query):
        try:
            if not path:
                return self.json_response({
                    "service": "Message Broker (Mosquitto)",
                    "status": "active" if self.mosquitto.is_running() else "stopped",
                    "description": "MQTT Message Broker - manages Mosquitto and monitors traffic",
                    "endpoints": {
                        "GET /": "Service info",
                        "GET /health": "Health check",
                        "GET /stats": "Traffic statistics",
                        "GET /config": "Broker configuration"
                    }
                })

            endpoint = path[0]

            if endpoint == "health":
                running = self.mosquitto.is_running()
                return self.json_response({
                    "status": "healthy" if running else "unhealthy",
                    "timestamp": time.time(),
                    "mosquitto": {
                        "running": running,
                        "host": self.broker_host,
                        "port": self.broker_port
                    },
                    "monitor": {
                        "connected": self.monitor.connected,
                        "messages_tracked": self.monitor.stats["messages_monitored"]
                    }
                })

            elif endpoint == "stats":
                return self.json_response({
                    "service": "Message Broker",
                    "uptime": time.time() - self.start_time,
                    "mosquitto": self.mosquitto.get_info(),
                    "monitor": self.monitor.get_stats()
                })

            elif endpoint == "config":
                return self.json_response({
                    "broker": self.broker_host,
                    "port": self.broker_port,
                    "qos": int(os.environ["MQTT_QOS"]),
                    "keep_alive": int(os.environ["MQTT_KEEP_ALIVE"]),
                    "topics": {
                        "measurements": "sectors/+/pipelines/+/measurements",
                        "valve_commands": "sectors/{sector}/pipelines/{id}/commands/valves",
                        "alerts": "sectors/{sector}/pipelines/{id}/alerts/{type}",
                        "telegram_commands": "telegram/commands/{pipeline_id}"
                    }
                })

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"Endpoint '{endpoint}' not found"})

        except Exception as e:
            logger.error(f"GET error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})

    def cleanup(self):
        self.monitor.stop()
        logger.info("Message Broker service stopped")


def main():
    port = int(os.environ["CHERRYPY_PORT"])
    host = os.environ["CHERRYPY_HOST"]
    service_name = os.environ["REGISTRATION_NAME"]
    service_desc = os.environ["SERVICE_DESCRIPTION"]
    catalog_url = os.environ["CATALOG_URL"]
    heartbeat_interval = int(os.environ["CATALOG_HEARTBEAT_INTERVAL"])

    cherrypy.config.update({
        'server.socket_host': host,
        'server.socket_port': port,
        'engine.autoreload.on': False
    })

    app_config = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', os.environ["CORS_ALLOW_ORIGIN"]),
                ('Access-Control-Allow-Methods', os.environ["CORS_ALLOW_METHODS"]),
                ('Access-Control-Allow-Headers', os.environ["CORS_ALLOW_HEADERS"]),
            ]
        }
    }

    service = MessageBrokerWebService()

    catalog_client = CatalogClient(catalog_url)
    registered = catalog_client.register_service(
        name=service_name,
        host=host,
        port=port,
        health_endpoint="/health",
        description=service_desc,
    )
    if registered:
        print_banner(
            "CATALOG REGISTERED",
            [
                f"svc:  {service_name}",
                f"addr: http://{host}:{port}",
                f"cat:  {catalog_url}",
                f"id:   {catalog_client.service_id}",
            ],
            kind="success",
        )
        catalog_client.start_heartbeat(
            name=service_name,
            host=host,
            port=port,
            description=service_desc,
            interval=heartbeat_interval,
        )
    else:
        print_banner(
            "CATALOG REGISTRATION FAILED",
            [
                f"svc:  {service_name}",
                f"cat:  {catalog_url}",
                f"why:  see logs above",
            ],
            kind="danger",
        )

    logger.info(f"Message Broker service on {host}:{port}")
    logger.info(f"Mosquitto running on {service.broker_host}:{service.broker_port}")

    cherrypy.quickstart(service, '/', app_config)


if __name__ == "__main__":
    main()
