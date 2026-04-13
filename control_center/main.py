import cherrypy
import json
import os
import sys
import time
import threading
import logging
from dotenv import load_dotenv


from decision_engine import DecisionEngine
from control_rules import ActionType
from auth_client import AuthClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_utils import CatalogClient

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ControlCenterWebService(object):
    # cherrypy rest api - tanin
    exposed = True

    def __init__(self):
        self.analytics_url = os.getenv("ANALYTICS_URL", "http://localhost:8083")
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        self.monitoring_interval = int(os.getenv("MONITORING_INTERVAL", 30))

        self.decision_engine = DecisionEngine(
            analytics_url=self.analytics_url,
            mqtt_broker=self.mqtt_broker,
            mqtt_port=self.mqtt_port
        )

        self.auth_client = AuthClient()

        self.monitoring_enabled = False
        self.monitoring_thread = None
        self.start_time = time.time()

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
                
                results = self.decision_engine.process_all_pipelines()
                
                for pipeline_id, pipeline_results in results.items():
                    for result in pipeline_results:
                        if result.decision.action != ActionType.NO_ACTION:
                            logger.info(
                                f"Action taken for {pipeline_id}/{result.bolt_id}: "
                                f"{result.decision.action.value} - {result.decision.reason}"
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

            elif endpoint == "history":
                user, error = self._require_auth("view_history")
                if error:
                    return error

                limit = int(query.get("limit", 100))
                return self.json_response({
                    "history": self.decision_engine.get_history(limit),
                    "total_decisions": len(self.decision_engine.decision_history)
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

                logger.info(f"Manual control: {action} valve {valve_id} in pipeline {pipeline_id}")

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
                    self.decision_engine.set_emergency_mode(True)
                    return self.json_response({
                        "message": "Emergency mode activated",
                        "timestamp": time.time()
                    })
                elif action == "deactivate":
                    logger.info("Emergency mode DEACTIVATED")
                    self.decision_engine.set_emergency_mode(False)
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
    port = int(os.getenv("CHERRYPY_PORT", 8085))
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
                ('Access-Control-Allow-Methods', 'GET, POST, DELETE'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            ]
        }
    }
    
    service = ControlCenterWebService()

    logger.info(f"Starting Control Center on {host}:{port}")
    logger.info("Features: Decision making, Analytics integration, Valve control")

    # inja un common utils ro import kon k sakhtamesh 
    catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
    catalog_client = CatalogClient(catalog_url)
    catalog_client.register_service(
        name="control_center",
        host=host,
        port=port,
        health_endpoint="/health",
        description="Decision engine & automation service"
    )

    cherrypy.quickstart(service, '/', app_config)

if __name__ == "__main__":
    main()