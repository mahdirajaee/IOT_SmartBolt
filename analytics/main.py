import cherrypy
import json
import requests
import os
import time
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MyMQTT import MyMQTT

from analytics_engine import AnalyticsEngine
from mqtt_publisher import MQTTPublisher
from catalog_client import CatalogClient
from anomaly_detector import AnomalyDetector, Thresholds

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ostad gofte k bayad rate limiting ezafe konim

class AnalyticsWebService(object):
    
    exposed = True

    def __init__(self):
        self.timeseries_url = os.getenv("TIMESERIES_DB_URL", "http://localhost:8082")
        self.catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))

        # cache baraye in k har bar az db nakhoonim
        self.cache = {}
        self.cache_ttl = int(os.getenv("ANALYSIS_CACHE_TTL", 300))  # 5 min default
        self.max_data_points = int(os.getenv("MAX_DATA_POINTS", 1000))
        
        self.analytics_engine = AnalyticsEngine()
        self.catalog_client = CatalogClient(self.catalog_url)
        self.mqtt_publisher = MQTTPublisher(self.mqtt_broker, self.mqtt_port, catalog_client=self.catalog_client)

        self.thresholds = {
            "temperature": {
                "alert": float(os.getenv("ALERT_THRESHOLD_TEMP", 45.0)),
                "critical": float(os.getenv("CRITICAL_THRESHOLD_TEMP", 60.0))
            },
            "pressure": {
                "alert": float(os.getenv("ALERT_THRESHOLD_PRESSURE", 120.0)),
                "critical": float(os.getenv("CRITICAL_THRESHOLD_PRESSURE", 150.0))
            }
        }

        self.anomaly_detector = AnomalyDetector(thresholds=Thresholds(
            temp_min=float(os.getenv("TEMP_MIN", 20.0)),
            temp_normal_min=float(os.getenv("TEMP_NORMAL_MIN", 25.0)),
            temp_normal_max=float(os.getenv("TEMP_NORMAL_MAX", 40.0)),
            temp_max=self.thresholds["temperature"]["alert"],
            temp_critical=self.thresholds["temperature"]["critical"],
            pressure_min=float(os.getenv("PRESSURE_MIN", 60.0)),
            pressure_normal_min=float(os.getenv("PRESSURE_NORMAL_MIN", 90.0)),
            pressure_normal_max=float(os.getenv("PRESSURE_NORMAL_MAX", 110.0)),
            pressure_max=self.thresholds["pressure"]["alert"],
            pressure_critical=self.thresholds["pressure"]["critical"],
            rapid_change_temp=float(os.getenv("RAPID_CHANGE_TEMP", 10.0)),
            rapid_change_pressure=float(os.getenv("RAPID_CHANGE_PRESSURE", 20.0))
        ))

        self.alert_history = []
        self.max_alert_history = int(os.getenv("MAX_ALERT_HISTORY", 100))
        self.alert_lock = threading.Lock()  # thread safety

        self.mqtt_subscriber = MyMQTT("analytics-subscriber", self.mqtt_broker, self.mqtt_port, self)
        self.mqtt_connected = False
        self.monitoring_enabled = True
        self.monitoring_interval = 0

        self._initialize_service()
    
    def _initialize_service(self):
        # inja hame chiz ro setup mikonim - mqtt, catalog, etc
        try:
            if self.catalog_client.register_service(
                host=os.getenv("SERVICE_HOST", "localhost"),
                port=int(os.getenv("CHERRYPY_PORT", 8083))
            ):
                logger.info("Successfully registered with Catalog")

                # threshold ha ro az catalog begirim
                fetched_thresholds = self.catalog_client.get_thresholds()
                if fetched_thresholds:
                    self._update_thresholds(fetched_thresholds)
                    self._update_anomaly_thresholds(fetched_thresholds)
                    logger.info("Thresholds updated from Catalog")
            else:
                logger.warning("Could not register with Catalog, using defaults")
            
            if self.mqtt_publisher.connect():
                self.mqtt_publisher.start_publisher()
                logger.info("MQTT publisher connected and started")
            else:
                logger.warning("Could not connect to MQTT broker")

            self.start_mqtt_subscriber()
            
        except Exception as e:
            logger.error(f"Service initialization error: {e}")
    
    def _update_thresholds(self, thresholds_data):
        if "temperature" in thresholds_data:
            temp_thresholds = thresholds_data["temperature"]
            self.thresholds["temperature"]["alert"] = temp_thresholds.get("alert", 45.0)
            self.thresholds["temperature"]["critical"] = temp_thresholds.get("critical", 60.0)
        
        if "pressure" in thresholds_data:
            pressure_thresholds = thresholds_data["pressure"]
            self.thresholds["pressure"]["alert"] = pressure_thresholds.get("alert", 120.0)
            self.thresholds["pressure"]["critical"] = pressure_thresholds.get("critical", 150.0)
    
    def _update_anomaly_thresholds(self, thresholds_data):
        new_thresholds = Thresholds()

        if "temperature" in thresholds_data:
            temp = thresholds_data["temperature"]
            new_thresholds.temp_normal_min = temp.get("min_normal", temp.get("normal_min", 25.0))
            new_thresholds.temp_normal_max = temp.get("max_normal", temp.get("normal_max", 40.0))
            new_thresholds.temp_max = temp.get("alert", 45.0)
            new_thresholds.temp_critical = temp.get("critical", 60.0)

        if "pressure" in thresholds_data:
            pressure = thresholds_data["pressure"]
            new_thresholds.pressure_normal_min = pressure.get("min_normal", pressure.get("normal_min", 90.0))
            new_thresholds.pressure_normal_max = pressure.get("max_normal", pressure.get("normal_max", 110.0))
            new_thresholds.pressure_max = pressure.get("alert", 120.0)
            new_thresholds.pressure_critical = pressure.get("critical", 150.0)

        self.anomaly_detector.thresholds = new_thresholds

    def _parse_senml(self, data):
        bn = data.get("bn", "")
        bt = data.get("bt", time.time())
        entries = data.get("e", [])

        parts = bn.strip("/").split("/")
        sector_id = parts[1] if len(parts) >= 2 else "sector-unknown"
        pipeline_id = parts[3] if len(parts) >= 4 else "unknown"

        bolts = {}
        for entry in entries:
            name = entry.get("n", "")
            name_parts = name.split("/")
            if len(name_parts) < 2:
                continue

            device_id = name_parts[0]
            field = name_parts[1]

            if device_id.startswith("bolt_"):
                if device_id not in bolts:
                    bolts[device_id] = {}
                bolts[device_id][field] = entry.get("v", entry.get("vb", entry.get("vs")))

        return pipeline_id, sector_id, bt, bolts

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)

            if "/measurements" in topic:
                pipeline_id, sector_id, timestamp, bolts = self._parse_senml(data)

                for bolt_id, readings in bolts.items():
                    temperature = readings.get("temperature")
                    pressure = readings.get("pressure")

                    if temperature is None and pressure is None:
                        continue

                    logger.info(f"MQTT data received: {pipeline_id}/{bolt_id} - T:{temperature}°C P:{pressure}PSI")
                    self._analyze_realtime(pipeline_id, bolt_id, sector_id, temperature, pressure, timestamp)
        except Exception as e:
            logger.error(f"MQTT message error: {e}")

    def _analyze_realtime(self, pipeline_id, bolt_id, sector_id, temp, pressure, timestamp):
        if temp > self.thresholds["temperature"]["critical"]:
            self._store_alert({"pipeline_id": pipeline_id, "bolt_id": bolt_id, "sector_id": sector_id, "anomaly_type": "threshold_exceeded", "severity": "critical", "sensor_type": "temperature", "value": temp, "message": f"Temperature {temp:.1f}°C critical", "timestamp": timestamp})
        elif temp > self.thresholds["temperature"]["alert"]:
            self._store_alert({"pipeline_id": pipeline_id, "bolt_id": bolt_id, "sector_id": sector_id, "anomaly_type": "threshold_warning", "severity": "warning", "sensor_type": "temperature", "value": temp, "message": f"Temperature {temp:.1f}°C warning", "timestamp": timestamp})
        if pressure > self.thresholds["pressure"]["critical"]:
            self._store_alert({"pipeline_id": pipeline_id, "bolt_id": bolt_id, "sector_id": sector_id, "anomaly_type": "threshold_exceeded", "severity": "critical", "sensor_type": "pressure", "value": pressure, "message": f"Pressure {pressure:.1f} PSI critical", "timestamp": timestamp})
        elif pressure > self.thresholds["pressure"]["alert"]:
            self._store_alert({"pipeline_id": pipeline_id, "bolt_id": bolt_id, "sector_id": sector_id, "anomaly_type": "threshold_warning", "severity": "warning", "sensor_type": "pressure", "value": pressure, "message": f"Pressure {pressure:.1f} PSI warning", "timestamp": timestamp})

    def start_mqtt_subscriber(self):
        try:
            self.mqtt_subscriber.start()
            self.mqtt_subscriber.mySubscribe("sectors/+/pipelines/+/measurements")
            self.mqtt_connected = True
            logger.info("Analytics subscribed directly to sectors/+/pipelines/+/measurements")
        except Exception as e:
            logger.error(f"MQTT subscriber error: {e}")

    def _store_alert(self, alert_data):
        with self.alert_lock:
            alert_data["id"] = f"alert_{int(time.time() * 1000)}"  
            alert_data["created_at"] = time.time()
            self.alert_history.insert(0, alert_data)  
            if len(self.alert_history) > self.max_alert_history:
                self.alert_history = self.alert_history[:self.max_alert_history]
            logger.info(f"Alert stored: {alert_data.get('anomaly_type', 'unknown')} - {alert_data.get('pipeline_id')} ({alert_data.get('sensor_type', 'unknown')})")

        pipeline_id = alert_data.get("pipeline_id", "unknown")
        try:
            sector_id = alert_data.get("sector_id", "sector-unknown")
            alert_type = alert_data.get("anomaly_type", "unknown")
            topic = f"sectors/{sector_id}/pipelines/{pipeline_id}/alerts/{alert_type}"
            alert_mqtt = {
                "pipeline_id": pipeline_id,
                "bolt_id": alert_data.get("bolt_id"),
                "sector_id": alert_data.get("sector_id", "sector-unknown"),
                "alert_type": alert_data.get("anomaly_type"),
                "anomaly_type": alert_data.get("anomaly_type"),
                "severity": alert_data.get("severity"),
                "message": alert_data.get("message", ""),
                "description": alert_data.get("message", ""),
                "temperature": alert_data.get("value") if alert_data.get("sensor_type") == "temperature" else None,
                "pressure": alert_data.get("value") if alert_data.get("sensor_type") == "pressure" else None,
                "timestamp": alert_data.get("timestamp", time.time())
            }
            alert_mqtt["recipient_chat_ids"] = self.catalog_client.get_chat_ids_for_sector(sector_id) if self.catalog_client else []
            if self.mqtt_publisher.connected:
                self.mqtt_publisher.mqtt.myPublish(topic, alert_mqtt)
                logger.debug(f"Alert published to MQTT: {topic} for {len(alert_mqtt['recipient_chat_ids'])} recipients")
        except Exception as e:
            logger.error(f"Failed to publish alert to MQTT: {e}")

    def _get_alerts(self, pipeline_id=None, severity=None, limit=50):
        with self.alert_lock:
            alerts = self.alert_history.copy()
        if pipeline_id:
            alerts = [a for a in alerts if a.get("pipeline_id") == pipeline_id]
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]
        return alerts[:limit]

    
    def json_response(self, data):
        return json.dumps(data).encode('utf-8')

    def get_cached_or_fetch(self, cache_key, fetch_func):
        now = time.time()
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if now - timestamp < self.cache_ttl:
                return cached_data

        data = fetch_func()
        self.cache[cache_key] = (data, now)
        return data
    
    def fetch_timeseries_data(self, endpoint, params=None):
        try:
            url = f"{self.timeseries_url}/{endpoint}"
            response = requests.get(url, params=params or {}, timeout=10)
            if response.status_code == 200:
                return response.json().get('data', [])
            return []
        except Exception as e:
            logger.error(f"Error fetching data from {endpoint}: {e}")
            return []

    def _analyze_trend(self, pipeline_id, bolt_id):
        cache_key = f"trend_{pipeline_id}_{bolt_id}"

        def fetch():
            temp_data = self.fetch_timeseries_data("temperature", {
                "pipeline_id": pipeline_id, "bolt_id": bolt_id, "limit": 100
            })
            pressure_data = self.fetch_timeseries_data("pressure", {
                "pipeline_id": pipeline_id, "bolt_id": bolt_id, "limit": 100
            })
            return {
                "temperature_trend": self.analytics_engine.calculate_trend(temp_data, "temperature"),
                "pressure_trend": self.analytics_engine.calculate_trend(pressure_data, "pressure")
            }

        return self.get_cached_or_fetch(cache_key, fetch)

    def _analyze_anomalies(self, pipeline_id, bolt_id):
        cache_key = f"anomalies_{pipeline_id}_{bolt_id}"

        def fetch():
            pipelines = self.catalog_client.get_all_pipelines()
            pipeline_data = pipelines.get(pipeline_id, {})
            sector_id = pipeline_data.get("sector_id", "sector-unknown")

            temp_data = self.fetch_timeseries_data("temperature", {
                "pipeline_id": pipeline_id, "bolt_id": bolt_id, "limit": self.max_data_points
            })
            pressure_data = self.fetch_timeseries_data("pressure", {
                "pipeline_id": pipeline_id, "bolt_id": bolt_id, "limit": self.max_data_points
            })

            temp_values = [point.get("temperature", 0) for point in temp_data] if temp_data else []
            pressure_values = [point.get("pressure", 0) for point in pressure_data] if pressure_data else []

            anomaly_results = []
            if temp_values and pressure_values:
                for i, (temp, pressure) in enumerate(zip(temp_values[-10:], pressure_values[-10:])):
                    result = self.anomaly_detector.detect_anomaly(pipeline_id, bolt_id, temp, pressure)
                    if result.is_anomaly:
                        anomaly_results.append({
                            "index": i,
                            "type": result.anomaly_type.value if result.anomaly_type else "unknown",
                            "severity": result.severity.value if result.severity else "unknown",
                            "description": result.description,
                            "confidence": result.confidence,
                            "recommendations": result.recommendations,
                            "temperature": temp,
                            "pressure": pressure
                        })

            temp_anomalies = self.analytics_engine.detect_anomaly_patterns(
                temp_data, "temperature", self.thresholds["temperature"]["alert"]
            )
            pressure_anomalies = self.analytics_engine.detect_anomaly_patterns(
                pressure_data, "pressure", self.thresholds["pressure"]["alert"]
            )

            if temp_anomalies.get("severity") in ["high", "critical"]:
                self.mqtt_publisher.publish_anomaly_alert(pipeline_id, bolt_id, temp_anomalies, "temperature", sector_id)
            if pressure_anomalies.get("severity") in ["high", "critical"]:
                self.mqtt_publisher.publish_anomaly_alert(pipeline_id, bolt_id, pressure_anomalies, "pressure", sector_id)

            return {
                "detected_anomalies": anomaly_results,
                "temperature_anomalies": temp_anomalies,
                "pressure_anomalies": pressure_anomalies
            }

        return self.get_cached_or_fetch(cache_key, fetch)

    def _analyze_prediction(self, pipeline_id, bolt_id, sensor_type):
        cache_key = f"prediction_{pipeline_id}_{bolt_id}_{sensor_type}"

        def fetch():
            pipelines = self.catalog_client.get_all_pipelines()
            pipeline_data = pipelines.get(pipeline_id, {})
            sector_id = pipeline_data.get("sector_id", "sector-unknown")

            data = self.fetch_timeseries_data(sensor_type, {
                "pipeline_id": pipeline_id, "bolt_id": bolt_id, "limit": 100
            })
            values = [point.get(sensor_type, 0) for point in data]
            prediction = self.analytics_engine.predict_next_values(values)

            alert = self.mqtt_publisher.publish_prediction_alert(
                pipeline_id, bolt_id, prediction, sensor_type,
                threshold=self.thresholds.get(sensor_type, {}).get("alert"),
                sector_id=sector_id
            )
            return {
                "sensor_type": sensor_type,
                "current_values": values[-10:] if len(values) > 10 else values,
                "prediction": prediction,
                "alert_generated": alert is not None
            }

        return self.get_cached_or_fetch(cache_key, fetch)

    def GET(self, *path, **query):
        try:
            if not path:
                cherrypy.response.status = 404
                return self.json_response({"error": "Endpoint not found"})

            endpoint = path[0]

            if endpoint == "health":
                return self.json_response({
                    "status": "healthy",
                    "timestamp": time.time(),
                    "components": {
                        "mqtt_publisher": "connected" if self.mqtt_publisher.connected else "disconnected",
                        "catalog": "registered" if self.catalog_client.registered else "not_registered",
                        "monitoring": "active" if self.monitoring_enabled else "inactive",
                        "cache_size": len(self.cache)
                    }
                })

            elif endpoint == "risk":
                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")

                if not pipeline_id or not bolt_id:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id and bolt_id required"})

                cache_key = f"risk_{pipeline_id}_{bolt_id}"

                def fetch_risk_data():
                    pipelines = self.catalog_client.get_all_pipelines()
                    pipeline_data = pipelines.get(pipeline_id, {})
                    sector_id = pipeline_data.get("sector_id", "sector-unknown")

                    temp_data = self.fetch_timeseries_data("temperature", {
                        "pipeline_id": pipeline_id, "bolt_id": bolt_id, "limit": 200
                    })
                    pressure_data = self.fetch_timeseries_data("pressure", {
                        "pipeline_id": pipeline_id, "bolt_id": bolt_id, "limit": 200
                    })

                    temp_values = [point.get("temperature", 0) for point in temp_data]
                    pressure_values = [point.get("pressure", 0) for point in pressure_data]

                    temp_stats = self.analytics_engine.calculate_statistics(temp_values)
                    pressure_stats = self.analytics_engine.calculate_statistics(pressure_values)

                    temp_anomalies = self.analytics_engine.detect_anomaly_patterns(
                        temp_data, "temperature", self.thresholds["temperature"]["alert"]
                    )

                    risk_data = self.analytics_engine.calculate_risk_score(
                        temp_stats, pressure_stats, temp_anomalies
                    )

                    health_score = self.analytics_engine.calculate_health_score(
                        temp_stats, pressure_stats, temp_anomalies
                    )

                    if risk_data["risk_level"] in ["high", "critical"]:
                        self.mqtt_publisher.publish_risk_alert(pipeline_id, bolt_id, risk_data, sector_id)

                    return {
                        "pipeline_id": pipeline_id,
                        "bolt_id": bolt_id,
                        "risk_assessment": risk_data,
                        "health_score": health_score,
                        "temperature_stats": temp_stats,
                        "pressure_stats": pressure_stats,
                        "analysis_timestamp": time.time()
                    }

                return self.json_response(self.get_cached_or_fetch(cache_key, fetch_risk_data))

            elif endpoint == "summary":
                pipelines = self.catalog_client.get_all_pipelines()
                summary = {}

                for pipeline_id in pipelines.keys():
                    pipeline_devices = self.catalog_client.get_pipeline_devices(pipeline_id)
                    pipeline_summary = {
                        "bolts": {},
                        "overall_health": "unknown",
                        "alerts_count": 0
                    }

                    for bolt in pipeline_devices.get("bolts", []):
                        bolt_id = bolt.get("id")
                        if bolt_id:
                            bolt_summary = {
                                "last_temperature": bolt.get("last_temperature"),
                                "last_pressure": bolt.get("last_pressure"),
                                "status": bolt.get("status", "unknown")
                            }
                            pipeline_summary["bolts"][bolt_id] = bolt_summary

                    summary[pipeline_id] = pipeline_summary

                return self.json_response({
                    "pipelines_summary": summary,
                    "total_pipelines": len(summary),
                    "monitoring_active": self.monitoring_enabled,
                    "timestamp": time.time()
                })

            elif endpoint == "alerts":
                limit = int(query.get("limit", 50))
                pipeline_id = query.get("pipeline_id")
                severity = query.get("severity")
                alerts = self._get_alerts(pipeline_id=pipeline_id, severity=severity, limit=limit)
                return self.json_response({
                    "alerts": alerts,
                    "total": len(alerts),
                    "filters": {
                        "pipeline_id": pipeline_id,
                        "severity": severity,
                        "limit": limit
                    },
                    "timestamp": time.time()
                })

            elif endpoint == "prediction":
                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")
                sensor = query.get("sensor", "temperature")

                if not pipeline_id or not bolt_id:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id and bolt_id required"})

                result = self._analyze_prediction(pipeline_id, bolt_id, sensor)
                return self.json_response(result)

            elif endpoint == "statistics":
                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")
                sensor = query.get("sensor", "temperature")
                hours = int(query.get("hours", 24))

                if not pipeline_id or not bolt_id:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id and bolt_id required"})

                cache_key = f"statistics_{pipeline_id}_{bolt_id}_{sensor}_{hours}"

                def fetch_statistics():
                    data = self.fetch_timeseries_data(sensor, {
                        "pipeline_id": pipeline_id, "bolt_id": bolt_id,
                        "limit": self.max_data_points, "hours": hours
                    })
                    values = [point.get(sensor, 0) for point in data if point.get(sensor) is not None]
                    if not values:
                        return {
                            "pipeline_id": pipeline_id, "bolt_id": bolt_id,
                            "sensor": sensor, "hours": hours,
                            "statistics": None, "message": "No data available"
                        }
                    stats = self.analytics_engine.calculate_statistics(values)
                    last_point = data[0] if data else {}
                    last_ts = last_point.get("time")
                    stats["last_value"] = round(values[0], 2) if values else 0
                    stats["last_timestamp"] = last_ts
                    return {
                        "pipeline_id": pipeline_id, "bolt_id": bolt_id,
                        "sensor": sensor, "hours": hours, "statistics": stats
                    }

                return self.json_response(self.get_cached_or_fetch(cache_key, fetch_statistics))

            elif endpoint == "aggregated":
                measurement = query.get("measurement", "temperature")
                aggregation = query.get("aggregation", "mean")
                pipeline_id = query.get("pipeline_id")
                hours = int(query.get("hours", 24))
                window = query.get("window", "1h")

                cache_key = f"aggregated_{measurement}_{aggregation}_{pipeline_id}_{hours}"

                def fetch_aggregated():
                    params = {"limit": self.max_data_points, "hours": hours}
                    if pipeline_id:
                        params["pipeline_id"] = pipeline_id
                    data = self.fetch_timeseries_data(measurement, params)
                    values = [point.get(measurement, 0) for point in data if point.get(measurement) is not None]
                    agg_fns = {
                        "mean": lambda v: sum(v) / len(v) if v else 0,
                        "min": lambda v: min(v) if v else 0,
                        "max": lambda v: max(v) if v else 0,
                        "count": lambda v: len(v),
                    }
                    fn = agg_fns.get(aggregation, agg_fns["mean"])
                    result_data = []
                    if values:
                        result_data = [{"time": time.time(), "value": round(fn(values), 2),
                                        "pipeline_id": pipeline_id, "bolt_id": None}]
                    return {
                        "measurement": measurement, "aggregation": aggregation,
                        "window": window, "pipeline_id": pipeline_id,
                        "count": len(result_data), "data": result_data
                    }

                return self.json_response(self.get_cached_or_fetch(cache_key, fetch_aggregated))

            elif endpoint == "anomalies":
                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")

                if not pipeline_id or not bolt_id:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id and bolt_id required"})

                result = self._analyze_anomalies(pipeline_id, bolt_id)
                return self.json_response(result)

            elif endpoint == "trend":
                pipeline_id = query.get("pipeline_id")
                bolt_id = query.get("bolt_id")

                if not pipeline_id or not bolt_id:
                    cherrypy.response.status = 400
                    return self.json_response({"error": "pipeline_id and bolt_id required"})

                result = self._analyze_trend(pipeline_id, bolt_id)
                return self.json_response(result)

            else:
                cherrypy.response.status = 404
                return self.json_response({"error": f"Endpoint '{endpoint}' not found"})

        except Exception as e:
            logger.error(f"GET error: {e}")
            cherrypy.response.status = 500
            return self.json_response({"error": str(e)})
    
def main():
    logger.info("starting analytics service...")
    port = int(os.getenv("CHERRYPY_PORT", 8083))
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

    service = AnalyticsWebService()

    logger.info(f"Starting Analytics Service v2.0 on {host}:{port}")
    logger.info("Endpoints: GET /health, /risk, /summary, /alerts, /trend, /anomalies, /prediction, /statistics")

    cherrypy.quickstart(service, '/', app_config)

if __name__ == "__main__":
    main()