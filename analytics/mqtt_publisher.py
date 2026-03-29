import json
import os
import logging
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from MyMQTT import MyMQTT

logger = logging.getLogger(__name__)


class MQTTPublisher:
    def __init__(self, broker="localhost", port=1883):
        self.broker = broker
        self.port = port
        self.client_id = "analytics_publisher"

        self.mqtt = MyMQTT(self.client_id, self.broker, self.port, self)
        self.connected = False

    def notify(self, topic, payload):
        try:
            data = json.loads(payload)
            logger.debug(f"Analytics command received on {topic}: {data}")
        except Exception as e:
            logger.error(f"Error processing analytics command: {e}")

    def connect(self):
        try:
            self.mqtt.start()
            time.sleep(1)
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            return self.connected
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            return False

    def disconnect(self):
        self.mqtt.stop()
        self.connected = False
        logger.info("MQTT publisher disconnected")

    def start_publisher(self):
        logger.info("Alert publisher ready (using MyMQTT)")

    def queue_alert(self, alert_data):
        self._publish_alert(alert_data)

    def _publish_alert(self, alert):
        try:
            sector_id = alert.get('sector_id', 'sector-unknown')
            topic = f"sectors/{sector_id}/pipelines/{alert['pipeline_id']}/alerts/{alert['alert_type']}"
            self.mqtt.myPublish(topic, alert)
            logger.info(f"Alert published to {topic}")
        except Exception as e:
            logger.error(f"Error publishing alert: {e}")

    def publish_anomaly_alert(self, pipeline_id, bolt_id, anomaly_data, sensor_type, sector_id="sector-unknown"):
        alert = {
            "alert_type": "anomaly",
            "sector_id": sector_id,
            "pipeline_id": pipeline_id,
            "bolt_id": bolt_id,
            "sensor_type": sensor_type,
            "timestamp": time.time(),
            "severity": anomaly_data.get("severity", "unknown"),
            "pattern": anomaly_data.get("pattern", "unknown"),
            "anomaly_count": anomaly_data.get("anomaly_count", 0),
            "anomaly_rate": anomaly_data.get("anomaly_rate", 0),
            "message": f"Anomaly detected in {sensor_type} for {bolt_id} on pipeline {pipeline_id}"
        }
        self.queue_alert(alert)
        return alert

    def publish_threshold_alert(self, pipeline_id, bolt_id, sensor_type, value, threshold, sector_id="sector-unknown"):
        alert = {
            "alert_type": "threshold_exceeded",
            "sector_id": sector_id,
            "pipeline_id": pipeline_id,
            "bolt_id": bolt_id,
            "sensor_type": sensor_type,
            "timestamp": time.time(),
            "value": value,
            "threshold": threshold,
            "exceeded_by": round(value - threshold, 2),
            "message": f"{sensor_type.capitalize()} threshold exceeded: {value} > {threshold}"
        }
        self.queue_alert(alert)
        return alert

    def publish_risk_alert(self, pipeline_id, bolt_id, risk_data, sector_id="sector-unknown"):
        alert = {
            "alert_type": "risk_assessment",
            "sector_id": sector_id,
            "pipeline_id": pipeline_id,
            "bolt_id": bolt_id,
            "timestamp": time.time(),
            "risk_score": risk_data.get("risk_score", 0),
            "risk_level": risk_data.get("risk_level", "unknown"),
            "risk_factors": risk_data.get("risk_factors", []),
            "message": f"Risk level: {risk_data.get('risk_level')} (score: {risk_data.get('risk_score')})"
        }
        self.queue_alert(alert)
        return alert

    def publish_prediction_alert(self, pipeline_id, bolt_id, prediction_data, sensor_type, threshold=None, sector_id="sector-unknown"):
        predictions = prediction_data.get("predictions", [])
        if not predictions:
            return None

        max_predicted = max(predictions)
        if threshold is None:
            threshold = float(os.getenv("ALERT_THRESHOLD_TEMP", 45.0)) if sensor_type == "temperature" else float(os.getenv("ALERT_THRESHOLD_PRESSURE", 120.0))

        if max_predicted > threshold:
            alert = {
                "alert_type": "prediction_warning",
                "sector_id": sector_id,
                "pipeline_id": pipeline_id,
                "bolt_id": bolt_id,
                "sensor_type": sensor_type,
                "timestamp": time.time(),
                "predicted_values": predictions,
                "max_predicted": max_predicted,
                "threshold": threshold,
                "prediction_method": prediction_data.get("method", "unknown"),
                "confidence": prediction_data.get("confidence", 0),
                "message": f"Predicted {sensor_type} may exceed threshold: {max_predicted} > {threshold}"
            }
            self.queue_alert(alert)
            return alert
        return None

    def publish_health_alert(self, pipeline_id, bolt_id, health_score, health_status, sector_id="sector-unknown"):
        health_threshold = int(os.getenv("HEALTH_ALERT_THRESHOLD", 40))
        if health_score < health_threshold:
            alert = {
                "alert_type": "health_warning",
                "sector_id": sector_id,
                "pipeline_id": pipeline_id,
                "bolt_id": bolt_id,
                "timestamp": time.time(),
                "health_score": health_score,
                "health_status": health_status,
                "message": f"Poor health status detected: {health_status} (score: {health_score})"
            }
            self.queue_alert(alert)
            return alert
        return None
