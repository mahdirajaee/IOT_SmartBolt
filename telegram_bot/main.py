import cherrypy
import json, os
import logging
import time
import threading
import asyncio
from dotenv import load_dotenv

from mqtt_client import MQTTClient
from auth_client import AuthClient
from service_state import ServiceStateManager
from data_client import DataClient
from telegram_handler import TelegramBotHandler

load_dotenv()  

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "DEBUG")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramBotWebService(object):
    exposed = True
    
    def __init__(self):
        self.service_name = "telegram_bot"
        self.service_port = int(os.getenv("CHERRYPY_PORT", 8087))
        self.service_host = os.getenv("CHERRYPY_HOST", "localhost")
        
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        
        self.account_manager_url = os.getenv("ACCOUNT_MANAGER_URL", "http://localhost:8084")
        self.timeseries_url = os.getenv("TIMESERIES_DB_URL", "http://localhost:8082")
        self.analytics_url = os.getenv("ANALYTICS_URL", "http://localhost:8083")
        self.catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
        
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        
        self.mqtt_client = None
        self.auth_client = None
        self.state_manager = None
        self.data_client = None
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
            self.mqtt_client = MQTTClient(self.mqtt_broker, self.mqtt_port)
            if self.mqtt_client.connect():
                logger.info("MQTT client connected")
            else:
                logger.error("Failed to connect MQTT client")
            
            self.auth_client = AuthClient(self.account_manager_url)
            logger.info("Authentication client initialized")

            self.data_client = DataClient(
                timeseries_url=self.timeseries_url,
                analytics_url=self.analytics_url,
                catalog_url=self.catalog_url
            )
            logger.info("Data client initialized")

            self.state_manager = ServiceStateManager(data_client=self.data_client)
            logger.info("Service state manager initialized")
            
            self._register_with_catalog()

            if self.telegram_token:
                self._start_telegram_bot()
            else:
                logger.warning("Telegram bot token not configured")
            
            self._start_health_monitor()
            
        except Exception as e:
            logger.error(f"Service initialization error: {e}")
    
    def _register_with_catalog(self):
        try:
            from common_utils import CatalogClient
            client = CatalogClient(self.catalog_url)
            if client.register_service(
                name=self.service_name,
                host=self.service_host,
                port=self.service_port,
                description="Telegram bot interface for IoT monitoring"
            ):
                logger.info("Registered with Resource Catalog")
            else:
                logger.warning("Could not register with Resource Catalog")
        except Exception as e:
            logger.warning(f"Resource Catalog not available: {e}")
    
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

                time.sleep(60)
        
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
                        "resource_catalog": self.catalog_url
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
    port = int(os.getenv("CHERRYPY_PORT", 8087))
    host = os.getenv("CHERRYPY_HOST", "0.0.0.0")
    
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
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST'),
                ('Access-Control-Allow-Headers', 'Content-Type')
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