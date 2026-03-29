import cherrypy
import json
import os
import time
import signal
import sys
import logging
from dotenv import load_dotenv

from sensor_simulator import SensorSimulator
from pipeline_manager import PipelineManager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common_utils import CatalogClient

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RaspberryPiWebService(object):
    
    exposed = True
    
    def __init__(self):
        self.simulator = SensorSimulator()
        self.pipeline_manager = self.simulator.pipeline_manager
        self.start_time = time.time()
        self.service_port = int(os.getenv("SERVICE_PORT", 8086))
        
        if not self.simulator.initialize():
            logger.error("Failed to initialize sensor simulator")
        else:
            self.simulator.start()
            logger.info(f"Raspberry Pi service started on port {self.service_port}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def GET(self, *path, **query):
        
        if not path:
            return {
                "service": "Raspberry Pi Sensor Simulator v2.0",
                "status": "active" if self.simulator.running else "stopped",
                "uptime": time.time() - self.start_time,
                "endpoints": {
                    "info": "/",
                    "health": "/health",
                    "status": "/status",
                    "pipelines": "/pipelines",
                    "data": "/data/<pipeline_id>",
                    "control": "/control",
                    "sync": "/sync",
                    "sync_catalog": "/sync/catalog"
                }
            }
        
        endpoint = path[0]
        
        if endpoint == "health":
            status = self.simulator.get_status()
            return {
                "status": "healthy" if self.simulator.running else "degraded",
                "timestamp": time.time(),
                "components": {
                    "simulator": "running" if self.simulator.running else "stopped",
                    "mqtt": "connected" if status["mqtt"]["connected"] else "disconnected",
                    "pipelines": f"{status['pipelines']['active_pipelines']} active"
                },
                "statistics": status["simulation"]
            }
        
        elif endpoint == "status":
            status = self.simulator.get_status()
            status["catalog_sync"] = {
                "enabled": True,
                "last_sync": self.pipeline_manager.last_sync_time,
                "sync_interval": self.pipeline_manager.sync_interval,
                "sync_running": self.pipeline_manager.sync_running,
                "catalog_url": self.pipeline_manager.resource_catalog_url
            }
            return status
            
        elif endpoint == "data":
            pipeline_id = path[1] if len(path) > 1 else None
            if not pipeline_id:
                cherrypy.response.status = 400
                return {"error": "Pipeline ID required"}
            data = self.simulator.get_pipeline_data(pipeline_id)
            if data:
                return data
            else:
                cherrypy.response.status = 404
                return {"error": f"Pipeline {pipeline_id} not found"}
                
        elif endpoint == "pipelines":
            pipeline_id = path[1] if len(path) > 1 else None
            if pipeline_id:
                pipeline = self.pipeline_manager.get_pipeline(pipeline_id)
                if pipeline:
                    return pipeline.get_info()
                else:
                    cherrypy.response.status = 404
                    return {"error": f"Pipeline {pipeline_id} not found"}
            else:
                pipelines = self.pipeline_manager.get_all_pipelines()
                return {
                    "pipelines": {pid: p.get_info() for pid, p in pipelines.items()},
                    "statistics": self.pipeline_manager.get_statistics()
                }

        elif endpoint == "sync":
            if len(path) > 1 and path[1] == "catalog":
                success = self.pipeline_manager.sync_with_catalog()
                if success:
                    return {"message": "Catalog synchronization completed successfully"}
                else:
                    cherrypy.response.status = 500
                    return {"error": "Failed to synchronize with catalog"}
            else:
                return {
                    "last_sync": self.pipeline_manager.last_sync_time,
                    "sync_interval": self.pipeline_manager.sync_interval,
                    "catalog_url": self.pipeline_manager.resource_catalog_url,
                    "sync_running": self.pipeline_manager.sync_running
                }

        else:
            cherrypy.response.status = 404
            return {"error": f"Endpoint '{endpoint}' not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self, *path, **query):
        if not path:
            cherrypy.response.status = 400
            return {"error": "Endpoint required"}
            
        endpoint = path[0]
        
        if endpoint == "pipelines":
            data = cherrypy.request.json
            pipeline_id = data.get("id")
            sensors = data.get("sensors", [])
            valves = data.get("valves", [])
            
            if not pipeline_id:
                cherrypy.response.status = 400
                return {"error": "Pipeline ID required"}
            
            sensor_tuples = [(s.get("id"), s.get("type", "temp")) for s in sensors]
            valve_tuples = [(v.get("id"), v.get("state", "closed")) for v in valves]
            
            if self.pipeline_manager.add_pipeline(pipeline_id, sensor_tuples, valve_tuples):
                return {"message": f"Pipeline {pipeline_id} created successfully"}
            else:
                cherrypy.response.status = 409
                return {"error": f"Pipeline {pipeline_id} already exists"}
                
        elif endpoint == "control":
            data = cherrypy.request.json
            command = data.get("command")
            
            if command == "start":
                if self.simulator.start():
                    return {"message": "Simulator started"}
                else:
                    return {"message": "Simulator already running"}
            
            elif command == "stop":
                self.simulator.stop()
                return {"message": "Simulator stopped"}
            
            elif command == "reset":
                self.pipeline_manager.reset_all()
                return {"message": "All pipelines reset"}
            
            elif command == "reload":
                self.pipeline_manager.reload_configuration()
                return {"message": "Configuration reloaded"}
            
            else:
                cherrypy.response.status = 400
                return {"error": f"Unknown command: {command}"}
                
        else:
            cherrypy.response.status = 404
            return {"error": f"POST endpoint '{endpoint}' not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, *path, **query):
        # update stuff
        if not path:
            cherrypy.response.status = 400
            return {"error": "Endpoint required"}
            
        endpoint = path[0]
        
        if endpoint == "pipelines":
            pipeline_id = path[1] if len(path) > 1 else None
            if not pipeline_id:
                cherrypy.response.status = 400
                return {"error": "Pipeline ID required"}
            
            data = cherrypy.request.json
            status = data.get("status")
            
            if status:
                if self.pipeline_manager.update_pipeline_status(pipeline_id, status):
                    return {"message": f"Pipeline {pipeline_id} status updated to {status}"}
                else:
                    cherrypy.response.status = 404
                    return {"error": f"Pipeline {pipeline_id} not found"}
            else:
                cherrypy.response.status = 400
                return {"error": "No valid updates provided"}
                
        elif endpoint == "valves":
            valve_id = path[1] if len(path) > 1 else None
            if not valve_id:
                cherrypy.response.status = 400
                return {"error": "Valve ID required"}
            
            data = cherrypy.request.json
            pipeline_id = data.get("pipeline_id")
            state = data.get("state")
            
            if not all([pipeline_id, state]):
                cherrypy.response.status = 400
                return {"error": "Pipeline ID and state required"}
            
            if self.pipeline_manager.set_valve_state(pipeline_id, valve_id, state):
                return {"message": f"Valve {valve_id} set to {state}"}
            else:
                cherrypy.response.status = 404
                return {"error": f"Valve {valve_id} not found in pipeline {pipeline_id}"}
                
        else:
            cherrypy.response.status = 404
            return {"error": f"PUT endpoint '{endpoint}' not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def DELETE(self, *path, **query):
        if not path:
            cherrypy.response.status = 400
            return {"error": "Endpoint required"}
            
        endpoint = path[0]
        
        if endpoint == "pipelines":
            pipeline_id = path[1] if len(path) > 1 else None
            if not pipeline_id:
                cherrypy.response.status = 400
                return {"error": "Pipeline ID required"}
            
            if self.pipeline_manager.remove_pipeline(pipeline_id):
                return {"message": f"Pipeline {pipeline_id} deleted successfully"}
            else:
                cherrypy.response.status = 404
                return {"error": f"Pipeline {pipeline_id} not found"}
                
        else:
            cherrypy.response.status = 404
            return {"error": f"DELETE endpoint '{endpoint}' not found"}
    

def signal_handler(signum, frame):
   
    logger.info("Shutdown signal received")
    cherrypy.engine.exit()
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    service_port = int(os.getenv("SERVICE_PORT", 8086))
    service_host = os.getenv("CHERRYPY_HOST", "127.0.0.1")
    config = {
        'global': {
            'server.socket_host': service_host,
            'server.socket_port': service_port,
            'server.thread_pool': 10,
            'server.socket_queue_size': 5,
            'engine.autoreload.on': False,
            'log.screen': False,
            'log.access_file': '',
            'log.error_file': ''
        },
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
    
    logger.info("Starting Raspberry Pi Service")
    app = RaspberryPiWebService()
    
    cherrypy.config.update(config['global'])
    
    cherrypy.tree.mount(app, '/', config)

    catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
    catalog_client = CatalogClient(catalog_url)
    catalog_client.register_service(
        name="raspberry_pi",
        host=service_host,
        port=service_port,
        health_endpoint="/health",
        description="Sensor simulation & control service"
    )

    cherrypy.engine.start()
    logger.info(f"Raspberry Pi Service running on port {service_port}")

    cherrypy.engine.block()
