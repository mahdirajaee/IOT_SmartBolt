
import statistics
import math
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    def __init__(self):
        self.anomaly_window = 10  # last 10 points
        self.prediction_window = 5  # predict next 5
        
    def calculate_moving_average(self, values, window_size=5):
        if len(values) < window_size:
            return values

        moving_averages = []
        for i in range(len(values) - window_size + 1):
            window = values[i:i + window_size]
            moving_averages.append(sum(window) / window_size)

        return moving_averages

    def calculate_trend(self, data_points, value_key):
        if len(data_points) < 2:
            return {"trend": "insufficient_data", "slope": 0, "confidence": 0}
        
        values = [point.get(value_key, 0) for point in data_points]
        x_values = list(range(len(values)))
        
        n = len(values)
        sum_x = sum(x_values)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_values, values))
        sum_x2 = sum(x * x for x in x_values)
        
        denominator = (n * sum_x2 - sum_x * sum_x)
        if denominator == 0:
            return {"trend": "undefined", "slope": 0, "confidence": 0}
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        y_mean = sum_y / n
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, values))

        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        if abs(slope) < 0.01:
            trend = "stable"
        elif slope > 0.5:
            trend = "rapidly_increasing"
        elif slope > 0.1:
            trend = "increasing"
        elif slope < -0.5:
            trend = "rapidly_decreasing"
        elif slope < -0.1:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "slope": round(slope, 4),
            "confidence": round(r_squared * 100, 2),
            "intercept": round(intercept, 2)
        }
    
    def calculate_statistics(self, values):
        if not values:
            return {}

        mean_val = statistics.mean(values)
        median_val = statistics.median(values)

        percentile_25 = sorted(values)[int(len(values) * 0.25)] if len(values) > 3 else min(values)
        percentile_75 = sorted(values)[int(len(values) * 0.75)] if len(values) > 3 else max(values)
        
        return {
            "min": min(values),
            "max": max(values),
            "mean": round(mean_val, 2),
            "median": round(median_val, 2),
            "std_dev": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
            "variance": round(statistics.variance(values), 2) if len(values) > 1 else 0,
            "percentile_25": round(percentile_25, 2),
            "percentile_75": round(percentile_75, 2),
            "iqr": round(percentile_75 - percentile_25, 2),
            "count": len(values)
        }
    
    def detect_anomalies_zscore(self, values, threshold=2.5):
        if len(values) < 3:
            return []

        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)

        if std_dev == 0:
            return []  # all values same, no anomalies

        anomalies = []
        for i, value in enumerate(values):
            z_score = abs((value - mean) / std_dev)
            if z_score > threshold:
                #print(f"anomaly found: {value} z={z_score}")  # debug
                anomalies.append({
                    "index": i,
                    "value": value,
                    "z_score": round(z_score, 2),
                    "deviation": round(value - mean, 2)
                })

        return anomalies
    
    def detect_anomaly_patterns(self, data_points, value_key, static_threshold, dynamic_threshold_enabled=True):
        if not data_points:
            return {"anomaly_count": 0, "anomaly_rate": 0, "anomalies": [], "pattern": "no_data"}

        values = [point.get(value_key, 0) for point in data_points]
        timestamps = [point.get("time") for point in data_points]

        static_anomalies = []
        for i, (value, timestamp) in enumerate(zip(values, timestamps)):
            if value > static_threshold:
                static_anomalies.append({
                    "index": i,
                    "timestamp": timestamp,
                    "value": value,
                    "threshold_exceeded": round(value - static_threshold, 2),
                    "type": "static_threshold"
                })
        
        dynamic_anomalies = []
        if dynamic_threshold_enabled and len(values) >= 10:
            z_anomalies = self.detect_anomalies_zscore(values)
            for anomaly in z_anomalies:
                dynamic_anomalies.append({
                    "index": anomaly["index"],
                    "timestamp": timestamps[anomaly["index"]] if anomaly["index"] < len(timestamps) else None,
                    "value": anomaly["value"],
                    "z_score": anomaly["z_score"],
                    "type": "statistical"
                })
        
        all_anomalies = static_anomalies + dynamic_anomalies
        unique_indices = set(a["index"] for a in all_anomalies)
        
        pattern = self._detect_anomaly_pattern(unique_indices, len(values))
        
        return {
            "anomaly_count": len(unique_indices),
            "anomaly_rate": round(len(unique_indices) / len(values), 3) if values else 0,
            "static_anomalies": static_anomalies,
            "dynamic_anomalies": dynamic_anomalies,
            "pattern": pattern,
            "severity": self._calculate_severity(len(unique_indices), len(values))
        }
    
    def _detect_anomaly_pattern(self, anomaly_indices, total_points):
        if not anomaly_indices:
            return "none"

        if len(anomaly_indices) >= total_points * 0.5:
            return "persistent"

        sorted_indices = sorted(anomaly_indices)
        if len(sorted_indices) >= 3:
            consecutive_count = 1
            for i in range(1, len(sorted_indices)):
                if sorted_indices[i] - sorted_indices[i-1] == 1:
                    consecutive_count += 1
                    if consecutive_count >= 3:
                        return "consecutive"
                else:
                    consecutive_count = 1
        
        if len(anomaly_indices) >= 5:
            return "frequent"
        elif len(anomaly_indices) >= 2:
            return "occasional"
        else:
            return "isolated"
    
    def _calculate_severity(self, anomaly_count, total_points):
        if total_points == 0:
            return "unknown"
        
        rate = anomaly_count / total_points
        if rate >= 0.5:
            return "critical"
        elif rate >= 0.3:
            return "high"
        elif rate >= 0.1:
            return "medium"
        elif rate > 0:
            return "low"
        else:
            return "none"
    
    def calculate_correlation(self, values1, values2):
        if len(values1) < 2 or len(values2) < 2:
            return {"correlation": "insufficient_data", "coefficient": 0}

        min_len = min(len(values1), len(values2))
        values1 = values1[:min_len]
        values2 = values2[:min_len]

        try:
            correlation = statistics.correlation(values1, values2)
            
            if abs(correlation) >= 0.9:
                strength = "very_strong"
            elif abs(correlation) >= 0.7:
                strength = "strong"
            elif abs(correlation) >= 0.5:
                strength = "moderate"
            elif abs(correlation) >= 0.3:
                strength = "weak"
            else:
                strength = "negligible"
            
            direction = "positive" if correlation > 0 else "negative"
            
            return {
                "correlation": f"{strength}_{direction}",
                "coefficient": round(correlation, 4),
                "strength": strength,
                "direction": direction
            }
        except Exception as e:
            logger.error(f"Correlation calculation error: {e}")
            return {"correlation": "calculation_error", "coefficient": 0}
    
    def predict_next_values(self, values, num_predictions=5):
        if len(values) < 3:
            return {"predictions": [], "method": "insufficient_data"}

        ma_values = self.calculate_moving_average(values, min(5, len(values)))
        if not ma_values:
            ma_values = values

        recent_values = ma_values[-min(10, len(ma_values)):]
        trend_data = [{"value": v} for v in recent_values]
        trend_result = self.calculate_trend(trend_data, "value")
        
        if trend_result["confidence"] > 50:
            predictions = []
            last_value = recent_values[-1]
            for i in range(1, num_predictions + 1):
                predicted_value = last_value + (trend_result["slope"] * i)
                predictions.append(round(predicted_value, 2))
            
            return {
                "next_values": predictions,
                "trend": trend_result["trend"],
                "method": "linear_trend",
                "confidence": trend_result["confidence"],
                "slope": trend_result["slope"]
            }
        else:
            mean_value = statistics.mean(recent_values[-5:])
            std_dev = statistics.stdev(recent_values[-5:]) if len(recent_values) >= 2 else 0
            
            predictions = []
            for _ in range(num_predictions):
                predicted_value = mean_value + (std_dev * 0.1)
                predictions.append(round(predicted_value, 2))
            
            return {
                "next_values": predictions,
                "trend": trend_result["trend"],
                "method": "mean_based",
                "confidence": 30,
                "slope": trend_result.get("slope", 0)
            }
    
    def calculate_health_score(self, temp_stats, pressure_stats, anomaly_data):
        base_score = 100.0

        temp_mean = temp_stats.get("mean", 0)
        if temp_mean > 40:
            base_score -= min(20, (temp_mean - 40) * 2)
        elif temp_mean < 20:
            base_score -= min(10, (20 - temp_mean))
        
        temp_std = temp_stats.get("std_dev", 0)
        if temp_std > 5:
            base_score -= min(15, temp_std - 5)
        
        pressure_mean = pressure_stats.get("mean", 0)
        if pressure_mean > 110:
            base_score -= min(20, (pressure_mean - 110) * 0.5)
        elif pressure_mean < 90:
            base_score -= min(10, (90 - pressure_mean) * 0.5)
        
        pressure_std = pressure_stats.get("std_dev", 0)
        if pressure_std > 10:
            base_score -= min(15, (pressure_std - 10) * 1.5)
        
        anomaly_rate = anomaly_data.get("anomaly_rate", 0)
        base_score -= min(30, anomaly_rate * 100)
        
        severity = anomaly_data.get("severity", "none")
        severity_penalty = {
            "critical": 30,
            "high": 20,
            "medium": 10,
            "low": 5,
            "none": 0
        }
        base_score -= severity_penalty.get(severity, 0)
        
        return max(0, min(100, base_score))
    
    def calculate_risk_score(self, temp_data, pressure_data, anomaly_data):
        risk_factors = []

        if temp_data.get("mean", 0) > 45:
            risk_factors.append({"factor": "high_temperature", "weight": 0.3})
        if pressure_data.get("mean", 0) > 120:
            risk_factors.append({"factor": "high_pressure", "weight": 0.3})
        
        if temp_data.get("std_dev", 0) > 8:
            risk_factors.append({"factor": "unstable_temperature", "weight": 0.2})
        if pressure_data.get("std_dev", 0) > 15:
            risk_factors.append({"factor": "unstable_pressure", "weight": 0.2})
        
        anomaly_rate = anomaly_data.get("anomaly_rate", 0)
        if anomaly_rate > 0.2:
            risk_factors.append({"factor": "high_anomaly_rate", "weight": 0.4})
        elif anomaly_rate > 0.1:
            risk_factors.append({"factor": "moderate_anomaly_rate", "weight": 0.2})
        
        pattern = anomaly_data.get("pattern", "none")
        if pattern in ["persistent", "consecutive"]:
            risk_factors.append({"factor": f"{pattern}_anomalies", "weight": 0.3})
        
        total_weight = sum(rf["weight"] for rf in risk_factors)
        risk_score = min(100, total_weight * 100)
        
        if risk_score >= 70:
            risk_level = "critical"
        elif risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 30:
            risk_level = "medium"
        elif risk_score > 0:
            risk_level = "low"
        else:
            risk_level = "minimal"
        
        return {
            "risk_score": round(risk_score, 1),
            "risk_level": risk_level,
            "risk_factors": risk_factors
        }