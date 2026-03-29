import cherrypy
import json
import os
import time
import logging
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

from mqtt_subscriber import MQTTSubscriber
from influxdb3_storage import InfluxDB3Storage
from data_models import AggregationType

#certificate handling for gRPC on Windows
# Force gRPC to use the Windows CA bundle that worked with curl.exe
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = r"C:\certs\cacert.pem"
print(f"[DEBUG] Using CA bundle: {os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH']}")
#--------------------------------------------

load_dotenv()
load_dotenv(Path(__file__).resolve().with_name(".env"))

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TimeSeriesDBService(object):
    # cherrypy rest api for timeseries data
    exposed = True

    def __init__(self):
        logger.info("starting timeseries service...")
        self.influx_url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.influx_token = os.getenv("INFLUXDB_TOKEN", "")
        self.influx_org = os.getenv("INFLUXDB_ORG", "iot_org")
        self.influx_bucket_north = os.getenv("INFLUXDB_BUCKET_NORTH", "smartboltbucket-north")
        self.influx_bucket_south = os.getenv("INFLUXDB_BUCKET_SOUTH", "smartboltbucket-south")

        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        
        self.storage = None
        self.subscriber = None
        self.start_time = time.time()
        
        self._initialize_service()
    
    def _initialize_service(self):
        # influxdb connection
        try:
            self.storage = InfluxDB3Storage(
                url=self.influx_url,
                bucket_north=self.influx_bucket_north,
                bucket_south=self.influx_bucket_south,
                token=self.influx_token,
                org=self.influx_org
            )
            logger.info(f"InfluxDB v3 storage initialized")
        except Exception as e:
            logger.warning(f"Failed to connect to InfluxDB v3: {e} - using in-memory storage")
            self.storage = None

        try:
            self.subscriber = MQTTSubscriber(broker=self.mqtt_broker, port=self.mqtt_port)
            if self.storage:
                self.subscriber.set_storage_callback(self._handle_storage)
            if self.subscriber.start():
                logger.info("MQTT subscriber started successfully")
            else:
                logger.error("Failed to start MQTT subscriber")
            self._register_with_catalog()
        except Exception as e:
            logger.error(f"Service initialization error: {e}")
    
    def _register_with_catalog(self):
        try:
            import requests
            
            catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
            
            payload = {
                "name": "timeseries_db",
                "host": os.getenv("SERVICE_HOST", "localhost"),
                "port": int(os.getenv("CHERRYPY_PORT", 8082)),
                "health_endpoint": "/health",
                "description": "Time series database connector for IoT data"
            }
            
            response = requests.post(
                f"{catalog_url}/services/register",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("Registered with Resource Catalog")
            else:
                logger.warning(f"Could not register with Resource Catalog: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Resource Catalog not available: {e}")

    def _get_pipeline_ids_from_catalog(self):
        try:
            import requests
            catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
            response = requests.get(f"{catalog_url}/devices/pipelines", timeout=5)
            if response.status_code == 200:
                data = response.json()
                pipelines = data.get("pipelines", {})
                return list(pipelines.keys())
        except Exception as e:
            logger.warning(f"Could not fetch pipelines from catalog: {e}")
        fallback = os.getenv("FALLBACK_PIPELINE_IDS", "N1,N2,N3,S1,S2,S3")
        return fallback.split(",")

    def _handle_storage(self, data_type, data):
        # callback from mqtt subscriber
        if not self.storage:
            return

        try:
            if data_type == "sensor" or data_type == "temperature" or data_type == "pressure":
                self.storage.store_sensor_reading(data)
            elif data_type == "valve":
                self.storage.store_valve_status(data)
            elif data_type == "anomaly":
                self.storage.store_anomaly_event(data)

        except Exception as e:
            logger.error(f"Storage error: {e}")
    
    def json_response(self, data):
        return json.dumps(data).encode('utf-8')
    
    def GET(self, *path, **query):
        try:
            if not path:
                return self.json_response({
                    "service": "TimeSeriesDB Connector v2.0",
                    "status": "active",
                    "storage": "InfluxDB" if self.storage else "in-memory",
                    "uptime": time.time() - self.start_time,
                    "endpoints": {
                        "data": {
                            "temperature": "/temperature?pipeline_id={pipeline_id}&bolt_id={bolt_id}&limit={limit}",
                            "pressure": "/pressure?pipeline_id={pipeline_id}&bolt_id={bolt_id}&limit={limit}",
                            "alerts": "/alerts?pipeline_id={pipeline_id}&severity={severity}&hours={hours}"
                        },
                        "analytics": {
                            "statistics": "/statistics?pipeline_id={pipeline_id}&bolt_id={bolt_id}&sensor={sensor}&hours={hours}",
                            "aggregated": "/aggregated?measurement={measurement}&aggregation={mean|sum|min|max}&window={window}"
                        },
                        "monitoring": {
                            "health": "/health",
                            "stats": "/stats",
                            "summary": "/summary?pipeline_id={pipeline_id}"
                        }
                    }
                })
            
            endpoint = path[0]
            
            if endpoint == "health":
                return self.json_response({
                    "status": "healthy",
                    "timestamp": time.time(),
                    "components": {
                        "influxdb": "connected" if self.storage and self.storage.connected else "disconnected",
                        "mqtt": "connected" if self.subscriber and self.subscriber.connected else "disconnected"
                    },
                    "stats": {
                        "mqtt": self.subscriber.get_stats() if self.subscriber else {},
                        "storage": self.storage.get_stats() if self.storage else {}
                    }
                })
            
            elif endpoint == "stats":
                return self.json_response({
                    "service": "TimeSeriesDB Connector",
                    "uptime": time.time() - self.start_time,
                    "mqtt_stats": self.subscriber.get_stats() if self.subscriber else {},
                    "storage_stats": self.storage.get_stats() if self.storage else {}
                })
            
            elif endpoint in ("temperature", "pressure"):
                if not self.storage:
                    cherrypy.response.status = 503
                    return self.json_response({"error": "Storage not available"})

                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")
                limit = int(query.get("limit", 100))
                hours = int(query.get("hours", 24))

                start_time = datetime.now() - timedelta(hours=hours)

                data = self.storage.query_sensor_data(
                    measurement=endpoint,
                    pipeline_id=pipeline_id,
                    bolt_id=bolt_id,
                    start_time=start_time,
                    limit=limit
                )

                return self.json_response({
                    "measurement": endpoint,
                    "pipeline_id": pipeline_id,
                    "bolt_id": bolt_id,
                    "count": len(data),
                    "data": data
                })
            
            elif endpoint == "statistics":
                if not self.storage:
                    cherrypy.response.status = 503
                    return self.json_response({"error": "Storage not available"})
                
                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")
                sensor = query.get("sensor", "temperature")
                hours = int(query.get("hours", 24))
                
                if not all([pipeline_id, bolt_id]):
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id and bolt_id required"})
                
                stats = self.storage.query_statistics(
                    measurement=sensor,
                    pipeline_id=pipeline_id,
                    bolt_id=bolt_id,
                    hours=hours
                )
                
                if stats:
                    return self.json_response({
                        "pipeline_id": pipeline_id,
                        "bolt_id": bolt_id,
                        "sensor": sensor,
                        "hours": hours,
                        "statistics": stats.to_dict()
                    })
                else:
                    return self.json_response({
                        "pipeline_id": pipeline_id,
                        "bolt_id": bolt_id,
                        "sensor": sensor,
                        "hours": hours,
                        "statistics": None,
                        "message": "No data available"
                    })
            
            elif endpoint == "aggregated":
                if not self.storage:
                    cherrypy.response.status = 503
                    return self.json_response({"error": "Storage not available"})
                
                measurement = query.get("measurement", "temperature")
                aggregation = query.get("aggregation", "mean")
                window = query.get("window", "1h")
                pipeline_id = query.get("pipeline_id")
                hours = int(query.get("hours", 24))
                
                try:
                    agg_type = AggregationType(aggregation.upper())
                except:
                    agg_type = AggregationType.MEAN
                
                start_time = datetime.now() - timedelta(hours=hours)
                
                data = self.storage.query_aggregated_data(
                    measurement=measurement,
                    aggregation=agg_type,
                    window=window,
                    pipeline_id=pipeline_id,
                    start_time=start_time
                )
                
                return self.json_response({
                    "measurement": measurement,
                    "aggregation": aggregation,
                    "window": window,
                    "pipeline_id": pipeline_id,
                    "count": len(data),
                    "data": data
                })
            
            elif endpoint == "summary":
                if not self.storage:
                    cherrypy.response.status = 503
                    return self.json_response({"error": "Storage not available"})
                
                pipeline_id = query.get("pipeline_id")
                
                if pipeline_id:
                    summary = self.storage.get_pipeline_summary(pipeline_id)
                    return self.json_response(summary)
                else:
                    summaries = {}
                    pipeline_ids = self._get_pipeline_ids_from_catalog()
                    for pid in pipeline_ids:
                        summaries[pid] = self.storage.get_pipeline_summary(pid)

                    return self.json_response({
                        "pipelines": summaries,
                        "total_pipelines": len(summaries)
                    })
            
            elif endpoint == "alerts":
                if not self.storage:
                    cherrypy.response.status = 503
                    return self.json_response({"error": "Storage not available"})

                pipeline_id = query.get("pipeline_id")
                severity = query.get("severity")
                hours = int(query.get("hours", 24))
                limit = int(query.get("limit", 100))

                alerts = self.storage.query_alerts(
                    pipeline_id=pipeline_id,
                    severity=severity,
                    hours=hours,
                    limit=limit
                )

                return self.json_response({
                    "alerts": alerts,
                    "total": len(alerts),
                    "filters": {
                        "pipeline_id": pipeline_id,
                        "severity": severity,
                        "hours": hours,
                        "limit": limit
                    },
                    "timestamp": time.time()
                })

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"Endpoint '{endpoint}' not found"})
                
        except Exception as e:
            logger.error(f"GET error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})
    
    def POST(self, *args, **kwargs):
        cherrypy.response.status = 405
        return self.json_response({"error": "POST operations not supported"})
    
    def PUT(self, *args, **kwargs):
        cherrypy.response.status = 405
        return self.json_response({"error": "PUT operations not supported"})
    
    def DELETE(self, *args, **kwargs):
        cherrypy.response.status = 405
        return self.json_response({"error": "DELETE operations not supported for time series data"})
    
    def shutdown(self):
        logger.info("Shutting down TimeSeriesDB Service...")
        
        if self.subscriber:
            self.subscriber.stop()
        
        if self.storage:
            self.storage.close()
        
        logger.info("TimeSeriesDB Service stopped")

def main():
    port = int(os.getenv("CHERRYPY_PORT", 8082))
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
                ('Access-Control-Allow-Headers', 'Content-Type')
            ]
        }
    }
    
    service = TimeSeriesDBService()
    
    logger.info(f"Starting TimeSeriesDB Connector v2.0 on {host}:{port}")
    logger.info("Features: MQTT subscription, InfluxDB storage, REST API")
    
    cherrypy.quickstart(service, '/', app_config)

if __name__ == "__main__":
    main()
