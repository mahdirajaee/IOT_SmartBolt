import cherrypy
import json
import os
import logging
from dotenv import load_dotenv
from service_registry import ServiceRegistry
from device_manager import DeviceManager
from config_manager import ConfigurationManager

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ResourceCatalogWebService(object):
    
    exposed = True

    def __init__(self):
        catalog_file = os.getenv('CATALOG_DATA_FILE', 'catalog.json')
        self.device_manager = DeviceManager(data_file=catalog_file)
        self.service_registry = ServiceRegistry(device_manager=self.device_manager)
        self.config_manager = ConfigurationManager()
        self.service_registry.start_health_checks()

    def json_response(self, data):
        return json.dumps(data).encode('utf-8')

    def GET(self, *path, **query):
        # not sure if we need all these endpoints
        try:
            #print(f"GET {path}")  # debug
            if not path:
                return self.json_response({
                    "service": "Resource Catalog",
                    "status": "active",
                    "endpoints": {
                        "catalog": {
                            "full": "/catalog",
                            "broker": "/broker"
                        },
                        "services": {
                            "list": "/services",
                            "register": "POST /services",
                            "health": "/services/health",
                            "by_name": "/services/{name}"
                        },
                        "devices": {
                            "list": "/devices",
                            "pipelines": "/devices/pipelines",
                            "bolts": "/devices/bolts",
                            "valves": "/devices/valves",
                            "by_pipeline": "/devices/pipeline/{id}"
                        },
                        "pipeline_bundles": {
                            "list": "/pipelines/bundle",
                            "get": "/pipelines/bundle/{id}",
                            "create": "POST /pipelines/bundle",
                            "update": "PUT /pipelines/bundle/{id}",
                            "delete": "DELETE /pipelines/bundle/{id}"
                        },
                        "users": {
                            "list": "/users",
                            "get": "/users/{id}",
                            "create": "POST /users",
                            "update": "PUT /users/{id}",
                            "delete": "DELETE /users/{id}"
                        },
                        "sectors": {
                            "list": "/sectors",
                            "get": "/sectors/{id}"
                        },
                        "config": {
                            "global": "/config/global",
                            "thresholds": "/config/thresholds",
                            "control_rules": "/config/rules",
                            "service": "/config/service/{name}"
                        }
                    }
                })

            resource = path[0]

            if resource == "catalog":
                return self.json_response(self.device_manager.get_full_catalog())

            elif resource == "broker":
                return self.json_response({"broker": self.device_manager.get_broker_config()})

            elif resource == "services":
                if len(path) == 1:
                    return self.json_response({
                        "services": self.service_registry.get_all_services()
                    })

                elif path[1] == "health":
                    services = self.service_registry.get_all_services()
                    health_status = {
                        sid: {
                            "name": service["name"],
                            "status": service["status"],
                            "last_heartbeat": service["last_heartbeat"]
                        }
                        for sid, service in services.items()
                    }
                    return self.json_response({"health_status": health_status})

                else:
                    service_name = path[1]
                    services = self.service_registry.get_services_by_name(service_name)
                    if services:
                        return self.json_response({"services": services})
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"Service '{service_name}' not found"})

            elif resource == "devices":
                if len(path) == 1:
                    return self.json_response({
                        "devices": self.device_manager.get_all_devices()
                    })

                elif path[1] == "pipelines":
                    return self.json_response({
                        "pipelines": self.device_manager.get_all_devices("pipelines")
                    })

                elif path[1] == "bolts":
                    return self.json_response({
                        "bolts": self.device_manager.get_all_devices("bolts")
                    })

                elif path[1] == "valves":
                    return self.json_response({
                        "valves": self.device_manager.get_all_devices("valves")
                    })

                elif path[1] == "pipeline" and len(path) > 2:
                    pipeline_id = path[2]
                    devices = self.device_manager.get_pipeline_devices(pipeline_id)
                    if devices:
                        return self.json_response(devices)
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"Pipeline '{pipeline_id}' not found"})

            elif resource == "pipelines":
                if len(path) >= 2 and path[1] == "bundle":
                    if len(path) == 2:
                        bundles = self.device_manager.get_all_pipeline_bundles()
                        return self.json_response({"pipeline_bundles": bundles})
                    elif len(path) == 3:
                        pipeline_id = path[2]
                        bundle = self.device_manager.get_pipeline_bundle(pipeline_id)
                        if bundle:
                            return self.json_response({"pipeline_bundle": bundle})
                        else:
                            cherrypy.response.status = 404
                            return self.json_response({"error": f"Pipeline bundle '{pipeline_id}' not found"})

            elif resource == "users":
                if len(path) == 1:
                    return self.json_response({"users": self.device_manager.get_users()})
                elif len(path) == 2:
                    try:
                        user_id = int(path[1])
                        user = self.device_manager.get_user(user_id)
                        if user:
                            return self.json_response({"user": user})
                        else:
                            cherrypy.response.status = 404
                            return self.json_response({"error": f"User '{user_id}' not found"})
                    except ValueError:
                        user = self.device_manager.get_user_by_name(path[1])
                        if user:
                            return self.json_response({"user": user})
                        else:
                            cherrypy.response.status = 404
                            return self.json_response({"error": f"User '{path[1]}' not found"})

            elif resource == "sectors":
                if len(path) == 1:
                    return self.json_response({"sectors": self.device_manager.get_sectors()})
                elif len(path) == 2:
                    sector_id = path[1]
                    sector = self.device_manager.get_sector(sector_id)
                    if sector:
                        return self.json_response({"sector": sector})
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"Sector '{sector_id}' not found"})

            elif resource == "config":
                if len(path) == 1:
                    return self.json_response({
                        "configurations": self.config_manager.get_all_configurations()
                    })

                elif path[1] == "global":
                    return self.json_response({
                        "global_config": self.config_manager.get_global_config()
                    })

                elif path[1] == "thresholds":
                    sensor_type = query.get("type")
                    return self.json_response({
                        "thresholds": self.config_manager.get_thresholds(sensor_type)
                    })

                elif path[1] == "rules":
                    rule_name = query.get("name")
                    return self.json_response({
                        "control_rules": self.config_manager.get_control_rules(rule_name)
                    })

                elif path[1] == "service" and len(path) > 2:
                    service_name = path[2]
                    config = self.config_manager.get_service_config(service_name)
                    return self.json_response({
                        "service": service_name,
                        "config": config
                    })

                elif len(path) > 1:
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"Config endpoint '{path[1]}' not found"})

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
                # TODO: maybe combine some of these?
                if len(path) > 1 and path[1] == "register":
                    service_name = input_data.get("name")
                    #print(f"registering {service_name}")  # debug
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

            elif resource == "devices":
                device_type = input_data.get("type")

                if device_type == "pipeline":
                    pipeline_id = input_data.get("id")
                    location = input_data.get("location", "")
                    description = input_data.get("description", "")
                    sector_id = input_data.get("sector_id", "")

                    if not pipeline_id:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "Pipeline ID required"})

                    self.device_manager.register_pipeline(pipeline_id, location, description, sector_id)
                    return self.json_response({
                        "message": "Pipeline registered",
                        "pipeline_id": pipeline_id
                    })

                elif device_type == "bolt":
                    bolt_id = input_data.get("id")
                    pipeline_id = input_data.get("pipeline_id")
                    bolt_type = input_data.get("bolt_type", "temperature_pressure")
                    location = input_data.get("location", "")

                    if not bolt_id or not pipeline_id:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "Bolt ID and pipeline ID required"})

                    self.device_manager.register_bolt(bolt_id, pipeline_id, bolt_type, location)
                    return self.json_response({
                        "message": "Bolt registered",
                        "bolt_id": bolt_id
                    })

                elif device_type == "valve":
                    valve_id = input_data.get("id")
                    pipeline_id = input_data.get("pipeline_id")
                    location = input_data.get("location", "")
                    normally_open = input_data.get("normally_open", True)

                    if not valve_id or not pipeline_id:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "Valve ID and pipeline ID required"})

                    self.device_manager.register_valve(valve_id, pipeline_id, location, normally_open)
                    return self.json_response({
                        "message": "Valve registered",
                        "valve_id": valve_id
                    })

            elif resource == "pipelines":
                if len(path) >= 2 and path[1] == "bundle":
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

            elif resource == "users":
                user_name = input_data.get("userName")
                user_id = input_data.get("userID")
                chat_id = input_data.get("chatID")
                password_hash = input_data.get("passwordHash")
                sectors = input_data.get("sectors", [])

                if not user_name or not user_id:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "userName and userID required"})

                success = self.device_manager.add_user(user_name, user_id, chat_id, sectors, password_hash)
                if success:
                    cherrypy.response.status = 201
                    return self.json_response({
                        "message": "User created successfully",
                        "userID": user_id
                    })
                else:
                    cherrypy.response.status = 409
                    return self.json_response({"error": f"User with ID '{user_id}' already exists"})

            elif resource == "config":
                if len(path) > 1 and path[1] == "service":
                    service_name = input_data.get("service")
                    config = input_data.get("config")

                    if not service_name or not config:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "Service name and config required"})

                    self.config_manager.set_service_config(service_name, config)
                    return self.json_response({
                        "message": "Service configuration set",
                        "service": service_name
                    })

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

            if resource == "devices":
                if len(path) > 1:
                    device_type = path[1]

                    if device_type == "bolt" and len(path) > 2:
                        bolt_id = path[2]
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

                    elif device_type == "valve" and len(path) > 2:
                        valve_id = path[2]
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
                if len(path) >= 3 and path[1] == "bundle":
                    pipeline_id = path[2]
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
                    try:
                        user_id = int(path[1])
                    except ValueError:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "Invalid user ID"})

                    updates = {}
                    if "userName" in input_data:
                        updates["userName"] = input_data["userName"]
                    if "chatID" in input_data:
                        updates["chatID"] = input_data["chatID"]
                    if "sectors" in input_data:
                        updates["sectors"] = input_data["sectors"]

                    if not updates:
                        cherrypy.response.status = 400
                        return self.json_response({"error": "No valid updates provided"})

                    success = self.device_manager.update_user(user_id, updates)
                    if success:
                        return self.json_response({
                            "message": "User updated successfully",
                            "userID": user_id
                        })
                    else:
                        cherrypy.response.status = 404
                        return self.json_response({"error": f"User '{user_id}' not found"})

            elif resource == "config":
                if len(path) > 1:
                    if path[1] == "global":
                        updates = input_data.get("updates", {})
                        self.config_manager.update_global_config(updates)
                        return self.json_response({
                            "message": "Global configuration updated"
                        })

                    elif path[1] == "thresholds":
                        sensor_type = input_data.get("sensor_type")
                        thresholds = input_data.get("thresholds")

                        if not sensor_type or not thresholds:
                            cherrypy.response.status = 400
                            return self.json_response({"error": "Sensor type and thresholds required"})

                        success = self.config_manager.update_thresholds(sensor_type, thresholds)
                        if success:
                            return self.json_response({
                                "message": "Thresholds updated",
                                "sensor_type": sensor_type
                            })
                        else:
                            cherrypy.response.status = 404
                            return self.json_response({"error": f"Sensor type '{sensor_type}' not found"})

                    elif path[1] == "rules":
                        rule_name = input_data.get("rule_name")
                        rule_config = input_data.get("rule_config")

                        if not rule_name or not rule_config:
                            cherrypy.response.status = 400
                            return self.json_response({"error": "Rule name and config required"})

                        self.config_manager.update_control_rule(rule_name, rule_config)
                        return self.json_response({
                            "message": "Control rule updated",
                            "rule_name": rule_name
                        })

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

            if resource == "services" and len(path) > 1:
                service_id = path[1]
                success = self.service_registry.unregister_service(service_id)

                if success:
                    return self.json_response({
                        "message": "Service unregistered",
                        "service_id": service_id
                    })
                else:
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"Service '{service_id}' not found"})

            elif resource == "devices" and len(path) > 2:
                device_type = path[1]
                device_id = path[2]

                success = self.device_manager.remove_device(device_type, device_id)
                if success:
                    return self.json_response({
                        "message": f"{device_type} removed",
                        "device_id": device_id
                    })
                else:
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"{device_type} '{device_id}' not found"})

            elif resource == "pipelines" and len(path) >= 3 and path[1] == "bundle":
                pipeline_id = path[2]
                success = self.device_manager.remove_pipeline_bundle(pipeline_id)
                if success:
                    return self.json_response({
                        "message": "Pipeline bundle removed successfully",
                        "pipeline_id": pipeline_id
                    })
                else:
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"Pipeline bundle '{pipeline_id}' not found"})

            elif resource == "users" and len(path) >= 2:
                try:
                    user_id = int(path[1])
                except ValueError:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "Invalid user ID"})

                success = self.device_manager.remove_user(user_id)
                if success:
                    return self.json_response({
                        "message": "User removed successfully",
                        "userID": user_id
                    })
                else:
                    cherrypy.response.status = 404
                    return self.json_response({"error": f"User '{user_id}' not found"})

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

    logger.info(f"Starting Resource Catalog service on {host}:{port}")
    cherrypy.quickstart(ResourceCatalogWebService(), '/', app_config)

if __name__ == "__main__":
    main()
