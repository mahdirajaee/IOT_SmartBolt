import cherrypy
import json
import os
import logging
import requests
import time
import sys
from dotenv import load_dotenv
from service_registry import ServiceRegistry
from device_manager import DeviceManager
from config_manager import ConfigurationManager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from internal_auth import resolve_internal_api_key

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CatalogWebService(object):

    exposed = True

    def __init__(self):
        catalog_file = os.getenv('CATALOG_DATA_FILE', 'catalog.json')
        self.device_manager = DeviceManager(data_file=catalog_file)
        self.service_registry = ServiceRegistry(device_manager=self.device_manager)
        self.config_manager = ConfigurationManager()
        self.account_manager_url = os.getenv("ACCOUNT_MANAGER_URL", "http://localhost:8084")
        self.internal_api_key = resolve_internal_api_key("catalog")
        self.service_registry.start_health_checks()

    def json_response(self, data):
        return json.dumps(data).encode('utf-8')

    def _internal_auth_headers(self):
        return {"X-Internal-API-Key": self.internal_api_key}

    def _proxy_account_manager(self, endpoint, params=None):
        try:
            response = requests.get(
                f"{self.account_manager_url}/internal/{endpoint}",
                params=params,
                headers=self._internal_auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return {"error": f"Account manager returned {response.status_code}"}
        except Exception as e:
            logger.error(f"Failed to proxy to account manager: {e}")
            return {"error": "Account manager unavailable"}

    def GET(self, *path, **query):
        try:
            if not path:
                return self.json_response({
                    "service": "Catalog",
                    "status": "active",
                    "endpoints": {
                        "services": {
                            "list_and_health": "GET /services",
                            "register": "POST /services/register",
                            "deregister": "DELETE /services/{id}"
                        },
                        "pipelines": {
                            "list": "GET /pipelines",
                            "detail": "GET /pipelines/{id}",
                            "create": "POST /pipelines",
                            "update": "PUT /pipelines/{id}",
                            "delete": "DELETE /pipelines/{id}"
                        },
                        "bolts": {
                            "update": "PUT /bolts/{id}"
                        },
                        "valves": {
                            "update": "PUT /valves/{id}"
                        },
                        "users": {
                            "list": "GET /users",
                            "get": "GET /users/{id}",
                            "update": "PUT /users/{id}"
                        },
                        "config": "GET /config[?section=global|thresholds|rules]"
                    }
                })

            resource = path[0]

            if resource == "health":
                return self.json_response({
                    "status": "healthy",
                    "service": "catalog",
                    "timestamp": time.time()
                })

            if resource == "services":
                if len(path) == 1:
                    services = self.service_registry.get_all_services()
                    health_status = {
                        sid: {
                            "name": service["name"],
                            "status": service["status"],
                            "last_heartbeat": service["last_heartbeat"]
                        }
                        for sid, service in services.items()
                    }
                    return self.json_response({
                        "services": services,
                        "health_status": health_status
                    })
                elif len(path) > 1 and path[1] != "register":
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"Endpoint '/services/{path[1]}' not found"})

            elif resource == "pipelines":
                if len(path) == 1:
                    return self.json_response({
                        "pipelines": self.device_manager.get_all_devices("pipelines"),
                        "pipeline_bundles": self.device_manager.get_all_pipeline_bundles()
                    })
                elif len(path) == 2:
                    pipeline_id = path[1]
                    devices = self.device_manager.get_pipeline_devices(pipeline_id)
                    if devices:
                        bundle = self.device_manager.get_pipeline_bundle(pipeline_id)
                        if bundle:
                            devices["pipeline_bundle"] = bundle
                        return self.json_response(devices)
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"Pipeline '{pipeline_id}' not found"})

            elif resource == "users":
                if len(path) == 1:
                    return self.json_response(self._proxy_account_manager("users"))
                elif len(path) == 2:
                    return self.json_response(self._proxy_account_manager(f"users/{path[1]}"))

            elif resource == "config":
                if len(path) > 1:
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"Use /config?section= instead of /config/{path[1]}"})
                section = query.get("section")
                if section == "global":
                    return self.json_response({
                        "global_config": self.config_manager.get_global_config()
                    })
                elif section == "thresholds":
                    sensor_type = query.get("type")
                    return self.json_response({
                        "thresholds": self.config_manager.get_thresholds(sensor_type)
                    })
                elif section == "rules":
                    rule_name = query.get("name")
                    return self.json_response({
                        "control_rules": self.config_manager.get_control_rules(rule_name)
                    })
                else:
                    return self.json_response({
                        "global_config": self.config_manager.get_global_config(),
                        "thresholds": self.config_manager.get_thresholds(),
                        "control_rules": self.config_manager.get_control_rules()
                    })

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"Resource '{resource}' not found"})

        except Exception as e:
            logger.error(f"GET error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})

    def POST(self, *path, **query):
        try:
            if not path:
                cherrypy.response.status = 400
                return self.json_response({"error": "Resource required"})

            resource = path[0]
            input_data = json.loads(cherrypy.request.body.read())

            if resource == "services":
                if len(path) > 1 and path[1] == "register":
                    service_name = input_data.get("name")
                    host = input_data.get("host", "localhost")
                    port = input_data.get("port")
                    health_endpoint = input_data.get("health_endpoint", "/health")
                    description = input_data.get("description", "")

                    if not service_name or not port:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "Service name and port required"})

                    service_id = self.service_registry.register_service(
                        service_name, host, port, health_endpoint, description
                    )

                    return self.json_response({
                        "message": "Service registered",
                        "service_id": service_id
                    })

            elif resource == "pipelines":
                if len(path) == 1:
                    pipeline_id = input_data.get("pipeline_id")
                    name = input_data.get("name", "")
                    location = input_data.get("location", "")
                    description = input_data.get("description", "")
                    sensor_limits = input_data.get("sensor_limits")
                    sector_id = input_data.get("sector_id", "")

                    if not pipeline_id:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "Pipeline ID required"})

                    bundle_info = self.device_manager.create_pipeline_bundle(
                        pipeline_id, name, location, description, sensor_limits, sector_id
                    )

                    if bundle_info:
                        cherrypy.response.status = 201
                        return self.json_response({
                            "message": "Pipeline bundle created successfully",
                            "bundle": bundle_info
                        })
                    else:
                        cherrypy.response.status = 409
                        return self.json_response({"error": f"Failed to create pipeline bundle '{pipeline_id}'. Pipeline may already exist."})

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"POST not supported for resource '{resource}'"})

        except Exception as e:
            logger.error(f"POST error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})

    def PUT(self, *path, **query):
        try:
            if not path:
                cherrypy.response.status = 400
                return self.json_response({"error": "Resource required"})

            resource = path[0]
            input_data = json.loads(cherrypy.request.body.read())

            if resource == "bolts":
                if len(path) >= 2:
                    bolt_id = path[1]
                    temperature = input_data.get("temperature")
                    pressure = input_data.get("pressure")

                    success = self.device_manager.update_bolt_data(bolt_id, temperature, pressure)
                    if success:
                        return self.json_response({
                            "message": "Bolt data updated",
                            "bolt_id": bolt_id
                        })
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"Bolt '{bolt_id}' not found"})

            elif resource == "valves":
                if len(path) >= 2:
                    valve_id = path[1]
                    state = input_data.get("state")
                    command = input_data.get("command")

                    success = self.device_manager.update_valve_state(valve_id, state, command)
                    if success:
                        return self.json_response({
                            "message": "Valve state updated",
                            "valve_id": valve_id
                        })
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"Valve '{valve_id}' not found"})

            elif resource == "pipelines":
                if len(path) >= 2:
                    pipeline_id = path[1]
                    updates = {}

                    if "name" in input_data:
                        updates["name"] = input_data["name"]
                    if "location" in input_data:
                        updates["location"] = input_data["location"]
                    if "description" in input_data:
                        updates["description"] = input_data["description"]
                    if "sensor_limits" in input_data:
                        updates["sensor_limits"] = input_data["sensor_limits"]
                    if "sector_id" in input_data:
                        updates["sector_id"] = input_data["sector_id"]

                    if not updates:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "No valid updates provided"})

                    success = self.device_manager.update_pipeline_bundle(pipeline_id, updates)
                    if success:
                        return self.json_response({
                            "message": "Pipeline bundle updated successfully",
                            "pipeline_id": pipeline_id
                        })
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"Pipeline bundle '{pipeline_id}' not found"})

            elif resource == "users":
                if len(path) >= 2:
                    user_id = path[1]
                    chat_id = input_data.get("chatID")
                    if chat_id is not None:
                        try:
                            resp = requests.put(
                                f"{self.account_manager_url}/internal/users/{user_id}",
                                json={"telegram_chat_id": str(chat_id)},
                                headers=self._internal_auth_headers(),
                                timeout=5
                            )
                            if resp.status_code == 200:
                                return self.json_response({"message": "User updated", "userID": user_id})
                            return self.json_response({"error": f"Account manager returned {resp.status_code}"})
                        except Exception as e:
                            logger.error(f"Failed to proxy PUT user: {e}")
                            return self.json_response({"error": "Account manager unavailable"})
                    return self.json_response({"error": "No valid updates"})

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"PUT not supported for resource '{resource}'"})

        except Exception as e:
            logger.error(f"PUT error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})

    def DELETE(self, *path, **query):
        try:
            if not path:
                cherrypy.response.status = 400
                return self.json_response({"error": "Resource required"})

            resource = path[0]

            if resource == "pipelines" and len(path) >= 2:
                pipeline_id = path[1]
                success = self.device_manager.remove_pipeline_bundle(pipeline_id)
                if success:
                    return self.json_response({
                        "message": "Pipeline bundle removed successfully",
                        "pipeline_id": pipeline_id
                    })
                else:
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"Pipeline bundle '{pipeline_id}' not found"})

            elif resource == "services" and len(path) >= 2:
                service_id = path[1]
                removed = self.service_registry.remove_service(service_id)
                if removed:
                    return self.json_response({
                        "message": "Service removed successfully",
                        "service_id": removed["service_id"],
                        "service_name": removed["name"]
                    })
                if self.device_manager.remove_service_from_catalog(service_id):
                    return self.json_response({
                        "message": "Service catalog entry removed successfully",
                        "service_id": service_id
                    })
                cherrypy.response.status = 404
                return self.json_response({"error": f"Service '{service_id}' not found"})

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"DELETE not supported for resource '{resource}'"})

        except Exception as e:
            logger.error(f"DELETE error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})

def main():
    port = int(os.getenv("CHERRYPY_PORT_CATALOG", os.getenv("CHERRYPY_PORT", 8081)))
    host = os.getenv("CHERRYPY_HOST_CATALOG", os.getenv("CHERRYPY_HOST", "0.0.0.0"))

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
                ('Access-Control-Allow-Headers', 'Content-Type')
            ]
        }
    }

    logger.info(f"Starting Catalog service on {host}:{port}")
    cherrypy.quickstart(CatalogWebService(), '/', app_config)

if __name__ == "__main__":
    main()
