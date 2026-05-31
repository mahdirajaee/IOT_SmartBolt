import cherrypy
import json, os
import sys
import logging
import time
import threading
import asyncio
import requests
from dotenv import load_dotenv

load_dotenv()

from service_log import print_banner
from mqtt_client import MQTTClient
from auth_client import AuthClient
from service_state import ServiceStateManager
from data_client import DataClient
from telegram_handler import TelegramBotHandler

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


class TelegramBotWebService(object):
    exposed = True

    def __init__(self):
        self.service_name = os.environ["REGISTRATION_NAME"]
        self.service_description = os.environ["SERVICE_DESCRIPTION"]
        self.service_port = int(os.environ["CHERRYPY_PORT"])
        self.service_host = os.environ["CHERRYPY_HOST"]

        self.mqtt_broker = os.environ["MQTT_BROKER"]
        self.mqtt_port = int(os.environ["MQTT_PORT"])

        self.account_manager_url = os.environ["ACCOUNT_MANAGER_URL"]
        self.timeseries_url = os.environ["TIMESERIES_DB_URL"]
        self.analytics_url = os.environ["ANALYTICS_URL"]
        self.catalog_url = os.environ["CATALOG_URL"]

        self.telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.health_monitor_interval = int(os.environ["HEALTH_MONITOR_INTERVAL"])
        self.catalog_heartbeat_interval = int(os.environ["CATALOG_HEARTBEAT_INTERVAL"])

        self.mqtt_client = MQTTClient(self.mqtt_broker, self.mqtt_port)
        self.auth_client = AuthClient(self.account_manager_url)
        self.data_client = DataClient(
            timeseries_url=self.timeseries_url,
            analytics_url=self.analytics_url,
            catalog_url=self.catalog_url
        )
        self.state_manager = ServiceStateManager(data_client=self.data_client)
        self.telegram_bot = None
        self.bot_thread = None
        self.bot_loop = None
        
        self.start_time = time.time()
        
        self.stats = {
            "messages_sent": 0,
            "commands_processed": 0,
            "alerts_received": 0,
            "errors": 0
        }

        self._initialize_service()
    
    def _initialize_service(self):
        try:
            if self.mqtt_client.connect():
                logger.info("MQTT client connected")
            else:
                logger.error("Failed to connect MQTT client")

            logger.info("Authentication client initialized")
            logger.info("Data client initialized")
            logger.info("Service state manager initialized")

            self._register_with_catalog()

            if self.telegram_token:
                self._start_telegram_bot()
            else:
                logger.warning("Telegram bot token not configured")

            self._start_health_monitor()

            print_banner(
                "TG STARTUP",
                [
                    f"mqtt:  {'connected' if self.mqtt_client and self.mqtt_client.connected else 'disconnected'}",
                    f"bot:   {'running' if self.telegram_token else 'no token'}",
                    f"port:  {self.service_port}",
                ],
                kind="info",
            )

        except Exception as e:
            logger.error(f"Service initialization error: {e}")
    
    def _register_with_catalog(self):
        try:
            client = CatalogClient(self.catalog_url)
            ok = client.register_service(
                name=self.service_name,
                host=self.service_host,
                port=self.service_port,
                description=self.service_description,
            )
            if ok:
                logger.info("Registered with Catalog")
                print_banner(
                    "CATALOG REGISTERED",
                    [
                        f"svc:  {self.service_name}",
                        f"addr: http://{self.service_host}:{self.service_port}",
                        f"cat:  {self.catalog_url}",
                        f"id:   {client.service_id}",
                    ],
                    kind="success",
                )
                client.start_heartbeat(
                    name=self.service_name,
                    host=self.service_host,
                    port=self.service_port,
                    description=self.service_description,
                    interval=self.catalog_heartbeat_interval,
                )
            else:
                logger.warning("Could not register with Catalog")
                print_banner(
                    "CATALOG REGISTRATION FAILED",
                    [
                        f"svc:  {self.service_name}",
                        f"cat:  {self.catalog_url}",
                        f"why:  catalog returned non-200",
                    ],
                    kind="danger",
                )
        except Exception as e:
            logger.warning(f"Catalog not available: {e}")
            print_banner(
                "CATALOG REGISTRATION FAILED",
                [
                    f"svc:  {self.service_name}",
                    f"cat:  {self.catalog_url}",
                    f"why:  {e}",
                ],
                kind="danger",
            )
    
    def _start_telegram_bot(self):
        
        async def async_bot_runner():
            self.telegram_bot = TelegramBotHandler(
                token=self.telegram_token,
                mqtt_client=self.mqtt_client,
                auth_client=self.auth_client,
                state_manager=self.state_manager,
                data_client=self.data_client
            )
            await self.telegram_bot.run()

        def run_bot():
            try:
                asyncio.run(async_bot_runner())
            except Exception as e:
                logger.error(f"Telegram bot error: {e}")
                import traceback
                traceback.print_exc()

        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        logger.info("Telegram bot started in background thread")
    
    def _start_health_monitor(self):
        def monitor_services():
            while True:
                try:
                    services_health = self.data_client.get_service_health()
                    if services_health and isinstance(services_health, dict):
                        health_status = services_health.get("health_status", services_health)
                        if isinstance(health_status, dict):
                            for service_name, health_data in health_status.items():
                                if isinstance(health_data, dict):
                                    self.state_manager.update_service_status(
                                        service_name,
                                        health_data.get("status", "unknown")
                                    )
                    pipelines = self.data_client.get_all_pipelines()
                    for pid in pipelines:
                        summary = self.data_client.get_pipeline_live_summary(pid)
                        if summary:
                            self.state_manager.update_pipeline_status(pid, summary)
                except Exception as e:
                    logger.error(f"Health monitor error: {e}")

                time.sleep(self.health_monitor_interval)

        monitor_thread = threading.Thread(target=monitor_services, daemon=True)
        monitor_thread.start()
        logger.info("Health monitor started")
    
    def json_response(self, data):
        return json.dumps(data).encode('utf-8')
    
    def _get_live_pipeline_data(self, pipeline_id=None):
        try:
            if pipeline_id:
                return self.data_client.get_pipeline_live_summary(pipeline_id) or {}

            summaries = {}
            for pid in self.data_client.get_all_pipelines():
                summary = self.data_client.get_pipeline_live_summary(pid)
                if summary:
                    summaries[pid] = summary
            return summaries

        except Exception as e:
            logger.error(f"Error fetching live pipeline data: {e}")
            if pipeline_id:
                return self.state_manager.get_pipeline_summary(pipeline_id)
            return {}
    
    def GET(self, *path, **query):
        try:
            if not path:
                return self.json_response({
                    "service": "Telegram Bot Service",
                    "status": "active",
                    "uptime": time.time() - self.start_time,
                    "telegram_bot": "running" if self.telegram_bot else "not configured",
                    "mqtt": "connected" if self.mqtt_client and self.mqtt_client.connected else "disconnected",
                    "endpoints": {
                        "health": "/health",
                        "stats": "/stats",
                        "alerts": "/alerts",
                        "config": "/config"
                    }
                })
            
            endpoint = path[0]
            
            if endpoint == "health":
                health = {
                    "status": "healthy",
                    "timestamp": time.time(),
                    "components": {
                        "mqtt": "connected" if self.mqtt_client and self.mqtt_client.connected else "disconnected",
                        "telegram_bot": "running" if self.telegram_bot else "not configured",
                        "services": self.state_manager.get_service_health() if self.state_manager else {}
                    }
                }
                return self.json_response(health)
            
            elif endpoint == "stats":
                stats = self.state_manager.get_statistics() if self.state_manager else {}
                stats.update({
                    "service_uptime": time.time() - self.start_time,
                    "mqtt_stats": self.mqtt_client.get_stats() if self.mqtt_client else {},
                    "cached_users": len(self.auth_client.session_cache) if self.auth_client else 0,
                    "alert_subscribers": len(self.telegram_bot.alert_subscribers) if self.telegram_bot else 0
                })
                return self.json_response(stats)
            
            elif endpoint == "alerts":
                limit = int(query.get("limit", 20))
                pipeline_id = query.get("pipeline_id")
                alerts = self.state_manager.get_recent_alerts(limit, pipeline_id) if self.state_manager else []
                return self.json_response({"alerts": alerts})
            
            elif endpoint == "config":
                config = {
                    "mqtt_broker": self.mqtt_broker,
                    "mqtt_port": self.mqtt_port,
                    "telegram_configured": bool(self.telegram_token),
                    "alert_cooldown": self.telegram_bot.alert_cooldown if self.telegram_bot else 30,
                    "services": {
                        "account_manager": self.account_manager_url,
                        "timeseries_db": self.timeseries_url,
                        "analytics": self.analytics_url,
                        "catalog": self.catalog_url
                    }
                }
                return self.json_response(config)
            
            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"Endpoint '{endpoint}' not found"})
                
        except Exception as e:
            logger.error(f"GET error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})
    
    def POST(self, *path, **query):
        try:
            if not path:
                cherrypy.response.status = 400
                return self.json_response({"error": "Endpoint required"})
            
            endpoint = path[0]
            input_data = json.loads(cherrypy.request.body.read())
            
            if endpoint == "alert":
                if self.state_manager:
                    self.state_manager.add_alert(input_data)
                return self.json_response({"message": "Alert added"})
            
            elif endpoint == "command":
                pipeline_id = input_data.get("pipeline_id")
                valve_id = input_data.get("valve_id")
                action = input_data.get("action")
                user_id = input_data.get("user_id")
                
                if not all([pipeline_id, valve_id, action]):
                    cherrypy.response.status = 400
                    return self.json_response({"error": "Missing required fields"})
                
                success = self.mqtt_client.send_valve_command(
                    pipeline_id, valve_id, action, user_id
                ) if self.mqtt_client else False

                if success:
                    if self.state_manager:
                        self.state_manager.add_command(input_data)
                    return self.json_response({"message": "Command sent", "success": True})
                else:
                    cherrypy.response.status = 500
                    return self.json_response({"error": "Failed to send command"})
            
            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"Endpoint '{endpoint}' not found"})
                
        except Exception as e:
            logger.error(f"POST error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})
    
    def cleanup(self):
        logger.info("Cleaning up Telegram Bot service...")
        
        if self.telegram_bot:
            self.telegram_bot.stop()
        
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        
        logger.info("Cleanup complete")

def main():
    port = int(os.environ["CHERRYPY_PORT"])
    host = os.environ["CHERRYPY_HOST"]

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
    
    service = TelegramBotWebService()
    
    def cleanup():
        service.cleanup()
    
    cherrypy.engine.subscribe('stop', cleanup)
    
    logger.info(f"Starting Telegram Bot service on {host}:{port}")
    cherrypy.quickstart(service, '/', app_config)

if __name__ == "__main__":
    main()