import cherrypy
import json
import os
import sys
import time
import threading
import logging
import requests
from dotenv import load_dotenv


from decision_engine import DecisionEngine
from control_rules import ActionType
from auth_client import AuthClient
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


class ControlCenterWebService(object):
    # cherrypy rest api - tanin
    exposed = True

    def __init__(self):
        self.analytics_url = os.environ["ANALYTICS_URL"]
        self.mqtt_broker = os.environ["MQTT_BROKER"]
        self.mqtt_port = int(os.environ["MQTT_PORT"])
        self.monitoring_interval = int(os.environ["MONITORING_INTERVAL"])

        self.decision_engine = DecisionEngine(
            analytics_url=self.analytics_url,
            mqtt_broker=self.mqtt_broker,
            mqtt_port=self.mqtt_port
        )

        self.auth_client = AuthClient()

        self.monitoring_enabled = False
        self.monitoring_thread = None
        self.start_time = time.time()
        self._tick = 0

        self._initialize_service()
        logger.info("control center starting...")

    def _initialize_service(self):
        try:
            if self.decision_engine.initialize():
                logger.info("Control Center initialized successfully")
                self.start_monitoring()
            else:
                logger.error("Failed to initialize Control Center")
                
        except Exception as e:
            logger.error(f"Service initialization error: {e}")
    
    def start_monitoring(self):
        # background thread for monitoring
        self.monitoring_enabled = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info(f"Monitoring started (interval: {self.monitoring_interval}s)")
    
    def stop_monitoring(self):
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitoring stopped")
    
    def _monitoring_loop(self):
        while self.monitoring_enabled:
            try:
                logger.debug("Running monitoring cycle")

                self._tick += 1
                actions_count = 0
                results = self.decision_engine.process_all_pipelines()

                for pipeline_id, pipeline_results in results.items():
                    for result in pipeline_results:
                        if result.decision.action != ActionType.NO_ACTION:
                            actions_count += 1
                            print_banner(
                                "DECISION",
                                [
                                    f"pipe:  {pipeline_id} / {result.bolt_id}",
                                    f"act:   {result.decision.action.value}",
                                    f"why:   {result.decision.reason}",
                                    f"ts:    {time.strftime('%H:%M:%S')}",
                                ],
                                kind="event",
                            )

                print_banner(
                    "CC TICK",
                    [
                        f"tick:  {self._tick}",
                        f"pipes: {len(results)}",
                        f"acts:  {actions_count}",
                        f"int:   {self.monitoring_interval}s",
                    ],
                    kind="info",
                )

                time.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(self.monitoring_interval)
    
    def _require_auth(self, required_action=None):
        auth_header = cherrypy.request.headers.get('Authorization', '')
        token = self.auth_client.extract_token_from_header(auth_header)
        if not token:
            cherrypy.response.status = 401
            return None, self.json_response({"error": "Authorization header required"})
        user = self.auth_client.validate_token(token)
        if not user:
            cherrypy.response.status = 401
            return None, self.json_response({"error": "Invalid or expired token"})
        if required_action and not self.auth_client.check_permission(user, required_action):
            cherrypy.response.status = 403
            return None, self.json_response({"error": "Insufficient permissions"})
        return user, None

    def json_response(self, data):
        return json.dumps(data).encode('utf-8')

    def GET(self, *path, **query):
        try:
            if not path:
                cherrypy.response.status = 404
                return self.json_response({"error": "Endpoint required"})

            endpoint = path[0]

            if endpoint == "health":
                return self.json_response({
                    "status": "healthy",
                    "timestamp": time.time(),
                    "components": {
                        "decision_engine": "active" if self.decision_engine.connected else "inactive",
                        "monitoring": "active" if self.monitoring_enabled else "inactive"
                    }
                })

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
            try:
                input_data = json.loads(cherrypy.request.body.read())
            except (json.JSONDecodeError, ValueError):
                cherrypy.response.status = 400
                return self.json_response({"error": "Invalid or missing JSON body"})

            if endpoint == "manual":
                user, error = self._require_auth("manual_control")
                if error:
                    return error

                pipeline_id = input_data.get("pipeline_id")
                valve_id = input_data.get("valve_id")
                action = input_data.get("action")
                reason = input_data.get("reason", "Manual control")

                if not all([pipeline_id, valve_id, action]):
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id, valve_id, and action required"})

                if action not in ("open", "close"):
                    cherrypy.response.status = 400
                    return self.json_response({"error": f"action must be 'open' or 'close', got {action!r}"})

                logger.info(f"Manual control: {action} valve {valve_id} in pipeline {pipeline_id}")

                print_banner(
                    "MANUAL OVERRIDE",
                    [
                        f"who:   {user.get('username', '?') if user else '?'}",
                        f"valve: {valve_id} -> {action}",
                        f"pipe:  {pipeline_id}",
                        f"why:   {reason}",
                    ],
                    kind="warning",
                )

                success = self.decision_engine.handle_manual_override(
                    pipeline_id, valve_id, action, reason
                )

                return self.json_response({
                    "success": success,
                    "pipeline_id": pipeline_id,
                    "valve_id": valve_id,
                    "action": action,
                    "reason": reason,
                    "timestamp": time.time()
                })

            elif endpoint == "emergency":
                user, error = self._require_auth("emergency_mode")
                if error:
                    return error

                action = input_data.get("action", "status")

                if action == "activate":
                    logger.warning("Emergency mode ACTIVATED")
                    print_banner(
                        "EMERGENCY ON",
                        [
                            f"by {user.get('username', '?') if user else '?'} @ {time.strftime('%H:%M:%S')}",
                            "cascade: venting — opening all valves now",
                        ],
                        kind="danger",
                    )
                    self.decision_engine.set_emergency_mode(True)
                    return self.json_response({
                        "message": "Emergency mode activated",
                        "timestamp": time.time()
                    })
                elif action == "deactivate":
                    logger.info("Emergency mode DEACTIVATED")
                    self.decision_engine.set_emergency_mode(False)
                    print_banner(
                        "EMERGENCY OFF",
                        [
                            f"by {user.get('username', '?') if user else '?'} @ {time.strftime('%H:%M:%S')}",
                        ],
                        kind="info",
                    )
                    return self.json_response({
                        "message": "Emergency mode deactivated",
                        "timestamp": time.time()
                    })
                else:
                    return self.json_response({
                        "emergency_mode": self.decision_engine.control_rules.emergency_mode,
                        "timestamp": time.time()
                    })

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"POST endpoint '{endpoint}' not found"})
                
        except Exception as e:
            logger.error(f"POST error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})
    
    def DELETE(self, *path, **query):
        cherrypy.response.status = 405
        return self.json_response({"error": "DELETE operations not supported"})

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
                ('Access-Control-Allow-Origin', os.environ['CORS_ALLOW_ORIGIN']),
                ('Access-Control-Allow-Methods', os.environ['CORS_ALLOW_METHODS']),
                ('Access-Control-Allow-Headers', os.environ['CORS_ALLOW_HEADERS'])
            ]
        }
    }
    
    service = ControlCenterWebService()

    logger.info(f"Starting Control Center on {host}:{port}")
    logger.info("Features: Decision making, Analytics integration, Valve control")

    # inja un common utils ro import kon k sakhtamesh
    catalog_url = os.environ["CATALOG_URL"]
    catalog_client = CatalogClient(catalog_url)
    registered = catalog_client.register_service(
        name="control_center",
        host=host,
        port=port,
        health_endpoint="/health",
        description="Decision engine & automation service"
    )
    if registered:
        print_banner(
            "CATALOG REGISTERED",
            [
                f"svc:  control_center",
                f"addr: http://{host}:{port}",
                f"cat:  {catalog_url}",
                f"id:   {catalog_client.service_id}",
            ],
            kind="success",
        )
        catalog_client.start_heartbeat(
            name="control_center",
            host=host,
            port=port,
            description="Decision engine & automation service",
            interval=int(os.environ["CATALOG_HEARTBEAT_INTERVAL"]),
        )
    else:
        print_banner(
            "CATALOG REGISTRATION FAILED",
            [
                f"svc:  control_center",
                f"cat:  {catalog_url}",
                f"why:  see logs above",
            ],
            kind="danger",
        )

    cherrypy.quickstart(service, '/', app_config)

if __name__ == "__main__":
    main()