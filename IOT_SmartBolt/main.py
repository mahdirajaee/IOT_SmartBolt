import cherrypy
import json
import os
import sys
import time
import threading
import logging
from dotenv import load_dotenv
from typing import Dict, Any

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

# age initialize start bokhore ,successful bude
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
    
    def json_response(self, data):
        return json.dumps(data).encode('utf-8')

    def require_auth(self, action='view_status'):
        # TO DO: double check this auth flow
        auth_header = cherrypy.request.headers.get('Authorization')
        if not auth_header:
            cherrypy.response.status = 401
            return None, {"error": "Authentication required"}

        token = self.auth_client.extract_token_from_header(auth_header)
        if not token:
            cherrypy.response.status = 401
            return None, {"error": "Invalid authorization header format"}

        user = self.auth_client.validate_token(token)
        if not user:
            cherrypy.response.status = 401
            return None, {"error": "Invalid or expired token"}

        if not self.auth_client.check_permission(user, action):
            cherrypy.response.status = 403
            return None, {"error": "Insufficient permissions", "required_action": action, "user_role": user.get('role')}

        return user, None

    def GET(self, *path, **query):
        # not sure if we need all these endpoints
        try:
            if not path:
                user, error = self.require_auth('view_status')
                if error:
                    return self.json_response(error)

                return self.json_response({
                    "service": "Control Center",
                    "status": "active",
                    "monitoring_enabled": self.monitoring_enabled,
                    "monitoring_interval": self.monitoring_interval,
                    "connected": self.decision_engine.connected,
                    "uptime": time.time() - self.start_time,
                    "timestamp": time.time(),
                    "endpoints": {
                        "health": "/health",
                        "decision": "/decision?pipeline_id={pipeline_id}&bolt_id={bolt_id}",
                        "manual": "/manual?pipeline_id={pipeline_id}&valve_id={valve_id}&action={open|close}",
                        "emergency": "/emergency?action=activate|deactivate",
                        "rules": "/rules",
                        "stats": "/stats",
                        "history": "/history?limit=100"
                    }
                })

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
            
            elif endpoint == "decision":
                user, error = self.require_auth('make_decision')
                if error:
                    return self.json_response(error)

                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")

                if not pipeline_id or not bolt_id:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id and bolt_id required"})

                logger.info(f"Decision requested by {user['username']} ({user['role']}) for pipeline {pipeline_id}, bolt {bolt_id}")

                result = self.decision_engine.make_decision(pipeline_id, bolt_id)

                if result:
                    return self.json_response({
                        "pipeline_id": result.pipeline_id,
                        "bolt_id": result.bolt_id,
                        "action": result.decision.action.value,
                        "reason": result.decision.reason,
                        "confidence": result.decision.confidence,
                        "rule": result.decision.rule_name,
                        "commands_sent": result.commands_sent,
                        "timestamp": result.timestamp,
                        "requested_by": user['username']
                    })
                else:
                    cherrypy.response.status = 500
                    return self.json_response({"error": "Could not make decision"})

            elif endpoint == "manual":
                user, error = self.require_auth('manual_control')
                if error:
                    return self.json_response(error)

                pipeline_id = query.get("pipeline_id")
                valve_id = query.get("valve_id")
                action = query.get("action")
                reason = query.get("reason", f"Manual control by {user['username']}")
                
                if not all([pipeline_id, valve_id, action]):
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id, valve_id, and action required"})
                
                logger.info(f"Manual control by {user['username']} ({user['role']}): {action} valve {valve_id} in pipeline {pipeline_id}")

                success = self.decision_engine.handle_manual_override(
                    pipeline_id, valve_id, action, reason
                )

                return self.json_response({
                    "success": success,
                    "pipeline_id": pipeline_id,
                    "valve_id": valve_id,
                    "action": action,
                    "reason": reason,
                    "timestamp": time.time(),
                    "executed_by": user['username']
                })
            
#emergency mode hatman bayad auth beshe
            elif endpoint == "emergency":
                user, error = self.require_auth('emergency_mode')
                if error:
                    return self.json_response(error)

                action = query.get("action", "status")

#faghat admin mitune in ghesmto faal kone
                if action == "activate":
                    logger.warning(f"Emergency mode ACTIVATED by {user['username']} ({user['role']})")
                    self.decision_engine.set_emergency_mode(True)
                    return self.json_response({
                        "message": "Emergency mode activated",
                        "timestamp": time.time(),
                        "activated_by": user['username']
                    })
                elif action == "deactivate":
                    logger.info(f"Emergency mode DEACTIVATED by {user['username']} ({user['role']})")
                    self.decision_engine.set_emergency_mode(False)
                    return self.json_response({
                        "message": "Emergency mode deactivated",
                        "timestamp": time.time(),
                        "deactivated_by": user['username']
                    })
                else:
                    return self.json_response({
                        "emergency_mode": self.decision_engine.control_rules.emergency_mode,
                        "timestamp": time.time()
                    })

            elif endpoint == "rules":
                user, error = self.require_auth('view_rules')
                if error:
                    return self.json_response(error)

                return self.json_response({
                    "rules": self.decision_engine.control_rules.get_rules_summary(),
                    "emergency_mode": self.decision_engine.control_rules.emergency_mode,
                    "override_mode": self.decision_engine.control_rules.override_mode
                })

            elif endpoint == "stats":
                user, error = self.require_auth('view_stats')
                if error:
                    return self.json_response(error)

                return self.json_response(self.decision_engine.get_stats())

            elif endpoint == "history":
                user, error = self.require_auth('view_history')
                if error:
                    return self.json_response(error)

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
            input_data = json.loads(cherrypy.request.body.read())
            
            if endpoint == "process":
                user, error = self.require_auth('process_pipeline')
                if error:
                    return self.json_response(error)

                pipeline_id = input_data.get("pipeline_id")

                if pipeline_id:
                    logger.info(f"Pipeline processing triggered by {user['username']} ({user['role']}) for pipeline {pipeline_id}")
                    results = self.decision_engine.process_pipeline(pipeline_id)

                    return self.json_response({
                        "pipeline_id": pipeline_id,
                        "decisions_made": len(results),
                        "results": [{
                            "bolt_id": r.bolt_id,
                            "action": r.decision.action.value,
                            "reason": r.decision.reason
                        } for r in results],
                        "timestamp": time.time(),
                        "triggered_by": user['username']
                    })
                else:
                    logger.info(f"All pipelines processing triggered by {user['username']} ({user['role']})")
                    results = self.decision_engine.process_all_pipelines()

                    summary = {}
                    for pipeline_id, pipeline_results in results.items():
                        summary[pipeline_id] = {
                            "decisions_made": len(pipeline_results),
                            "actions": [r.decision.action.value for r in pipeline_results]
                        }

                    return self.json_response({
                        "summary": summary,
                        "total_decisions": sum(len(r) for r in results.values()),
                        "timestamp": time.time(),
                        "triggered_by": user['username']
                    })
            
            elif endpoint == "monitoring":
                user, error = self.require_auth('modify_monitoring')
                if error:
                    return self.json_response(error)

                action = input_data.get("action")

                if action == "start":
                    if not self.monitoring_enabled:
                        logger.info(f"Monitoring started by {user['username']} ({user['role']})")
                        self.start_monitoring()
                    return self.json_response({
                        "message": "Monitoring started",
                        "monitoring_enabled": self.monitoring_enabled,
                        "modified_by": user['username']
                    })

                elif action == "stop":
                    if self.monitoring_enabled:
                        logger.warning(f"Monitoring stopped by {user['username']} ({user['role']})")
                        self.stop_monitoring()
                    return self.json_response({
                        "message": "Monitoring stopped",
                        "monitoring_enabled": self.monitoring_enabled,
                        "modified_by": user['username']
                    })

                else:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "Invalid action"})
            
            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"POST endpoint '{endpoint}' not found"})
                
        except Exception as e:
            logger.error(f"POST error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})
    
    def PUT(self, *path, **query):
        try:
            if not path:
                cherrypy.response.status = 400
                return self.json_response({"error": "Endpoint required"})
            
            endpoint = path[0]
            
            if endpoint == "cache":
                user, error = self.require_auth('clear_cache')
                if error:
                    return self.json_response(error)

                action = query.get("action")

#username ro log konim
                if action == "clear":
                    logger.info(f"Cache cleared by {user['username']} ({user['role']})")
                    self.decision_engine.clear_cache()
                    return self.json_response({
                        "message": "Cache cleared",
                        "timestamp": time.time(),
                        "cleared_by": user['username']
                    })
                else:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "Invalid action"})
                
            #ghanoonaye error endpoint
            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"PUT endpoint '{endpoint}' not found"})
                
        except Exception as e:
            logger.error(f"PUT error: {e}")
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
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE'),
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