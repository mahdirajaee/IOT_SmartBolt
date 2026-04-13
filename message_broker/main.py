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
from common_utils import CatalogClient

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BrokerMonitor:
    def __init__(self, broker, port):
        self.broker = broker
        self.port = port
        self.client_id = "message-broker-monitor"
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
            time.sleep(1)
            self.connected = True

            self.mqtt.mySubscribe("sectors/+/pipelines/+/measurements")
            self.mqtt.mySubscribe("sectors/+/pipelines/+/alerts/+")
            self.mqtt.mySubscribe("sectors/+/pipelines/+/commands/valves")
            self.mqtt.mySubscribe("telegram/commands/+")
            self.mqtt.mySubscribe("alerts/anomalies/+")

            logger.info("Broker monitor started - tracking all MQTT traffic")
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
        self.broker_host = os.getenv("MQTT_BROKER", "localhost")
        self.broker_port = int(os.getenv("MQTT_PORT", 1883))

    def is_running(self) -> bool:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.broker_host, self.broker_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def start(self) -> bool:
        if self.is_running():
            logger.info(f"Mosquitto already running on {self.broker_host}:{self.broker_port}")
            return True

        try:
            if self.system == "Darwin":
                subprocess.run(["brew", "services", "start", "mosquitto"], check=True)
            elif self.system == "Linux":
                subprocess.run(["sudo", "systemctl", "start", "mosquitto"], check=True)
            else:
                subprocess.Popen(["mosquitto", "-d"])

            time.sleep(2)
            running = self.is_running()
            if running:
                logger.info("Mosquitto started successfully")
            else:
                logger.error("Mosquitto failed to start")
            return running
        except Exception as e:
            logger.error(f"Error starting Mosquitto: {e}")
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
        self.broker_host = os.getenv("MQTT_BROKER", "localhost")
        self.broker_port = int(os.getenv("MQTT_PORT", 1883))

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
                    "qos": int(os.getenv("MQTT_QOS", 2)),
                    "keep_alive": int(os.getenv("MQTT_KEEP_ALIVE", 60)),
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
    port = int(os.getenv("CHERRYPY_PORT", 8089))
    host = os.getenv("CHERRYPY_HOST", "127.0.0.1")

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
                ('Access-Control-Allow-Origin', '*')
            ]
        }
    }

    service = MessageBrokerWebService()

    catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
    catalog_client = CatalogClient(catalog_url)
    catalog_client.register_service(
        name="message_broker",
        host=host,
        port=port,
        health_endpoint="/health",
        description="MQTT Message Broker (Mosquitto) manager and monitor"
    )

    logger.info(f"Message Broker service on {host}:{port}")
    logger.info(f"Mosquitto running on {service.broker_host}:{service.broker_port}")

    cherrypy.quickstart(service, '/', app_config)


if __name__ == "__main__":
    main()
