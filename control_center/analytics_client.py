import os
import requests
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AnalyticsInsight:
    pipeline_id: str
    risk_level: str
    anomalies: List[Dict[str, Any]]
    predictions: Dict[str, Any]
    recommendations: List[str]
    health_score: float
    timestamp: float

class AnalyticsClient:
    def __init__(self, analytics_url: str = "http://localhost:8083"):
        self.analytics_url = analytics_url
        # ino 60 konim behtre, vase mohammad be moshkel bar mikhore
        self.timeout = int(os.getenv("ANALYTICS_CLIENT_TIMEOUT", 10))
        self.cache = {}
        self.cache_ttl = int(os.getenv("ANALYTICS_CACHE_TTL", 60))

    def get_risk_assessment(self, pipeline_id: str, bolt_id: str) -> Optional[Dict[str, Any]]:
        try:
            cache_key = f"risk_{pipeline_id}_{bolt_id}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]["data"]
            response = requests.get(
                f"{self.analytics_url}/risk",
                params={"pipeline_id": pipeline_id, "bolt_id": bolt_id},
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                self._cache_data(cache_key, data)
                return data
            logger.error(f"Failed to get risk assessment: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching risk assessment: {e}")
        return None

    def get_anomalies(self, pipeline_id: str, bolt_id: str) -> Optional[Dict[str, Any]]:
        try:
            cache_key = f"anomalies_{pipeline_id}_{bolt_id}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]["data"]
            response = requests.get(
                f"{self.analytics_url}/anomalies",
                params={"pipeline_id": pipeline_id, "bolt_id": bolt_id},
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                self._cache_data(cache_key, data)
                return data
            logger.error(f"Failed to get anomalies: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching anomalies: {e}")
        return None

    def get_predictions(self, pipeline_id: str, bolt_id: str, sensor: str = "temperature") -> Optional[Dict[str, Any]]:
        try:
            cache_key = f"predictions_{pipeline_id}_{bolt_id}_{sensor}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]["data"]
            response = requests.get(
                f"{self.analytics_url}/prediction",
                params={"pipeline_id": pipeline_id, "bolt_id": bolt_id, "sensor": sensor},
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                self._cache_data(cache_key, data)
                return data
            logger.error(f"Failed to get predictions: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching predictions: {e}")
        return None

    def get_statistics(self, pipeline_id: str, bolt_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(
                f"{self.analytics_url}/statistics",
                params={"pipeline_id": pipeline_id, "bolt_id": bolt_id},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            logger.error(f"Failed to get statistics: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching statistics: {e}")
        return None

    def get_trend_analysis(self, pipeline_id: str, bolt_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(
                f"{self.analytics_url}/trend",
                params={"pipeline_id": pipeline_id, "bolt_id": bolt_id},
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            logger.error(f"Failed to get trend analysis: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching trend analysis: {e}")
        return None

    def get_pipeline_summary(self) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(f"{self.analytics_url}/summary", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            logger.error(f"Failed to get pipeline summary: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching pipeline summary: {e}")
        return None

    def get_comprehensive_insight(self, pipeline_id: str, bolt_id: str) -> Optional[AnalyticsInsight]:
        # in method hamechio combine mikone, logic ro double check kon lotfan
        try:
            risk = self.get_risk_assessment(pipeline_id, bolt_id)
            anomalies = self.get_anomalies(pipeline_id, bolt_id)
            predictions = self.get_predictions(pipeline_id, bolt_id, "temperature")

            if not risk:
                return None

            risk_assessment = risk.get("risk_assessment", {})
            health_score = risk.get("health_score", 0)

            detected_anomalies = []
            if anomalies:
                detected_anomalies = anomalies.get("detected_anomalies", [])
                if not detected_anomalies:
                    for sensor_type in ("temperature", "pressure"):
                        sensor_anomalies = anomalies.get(f"{sensor_type}_anomalies", {})
                        if sensor_anomalies.get("severity") in ["high", "critical"]:
                            detected_anomalies.append({
                                "type": f"high_{sensor_type}",
                                "sensor_type": sensor_type,
                                "severity": sensor_anomalies.get("severity"),
                                "pattern": sensor_anomalies.get("pattern")
                            })

            recommendations = []
            if risk_assessment.get("risk_level") in ["high", "critical"]:
                recommendations.append("Consider valve closure")
                recommendations.append("Monitor closely")

            pred_payload = predictions if isinstance(predictions, dict) else {}
            if pred_payload.get("prediction", {}).get("trend") == "increasing":
                recommendations.append("Prepare for potential threshold breach")

            return AnalyticsInsight(
                pipeline_id=pipeline_id,
                risk_level=risk_assessment.get("risk_level", "unknown"),
                anomalies=detected_anomalies,
                predictions=pred_payload.get("prediction", {}),
                recommendations=recommendations,
                health_score=health_score,
                timestamp=time.time()
            )

        except Exception as e:
            logger.error(f"Error getting comprehensive insight: {e}")
            return None

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self.cache:
            return False
        return (time.time() - self.cache[key]["timestamp"]) < self.cache_ttl

    def _cache_data(self, key: str, data: Any):
        self.cache[key] = {"data": data, "timestamp": time.time()}

    def clear_cache(self):
        self.cache.clear()
        logger.info("Analytics client cache cleared")
