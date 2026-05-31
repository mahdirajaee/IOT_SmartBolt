import os
import requests
import logging, time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
# TODO: add connection pooling? maybe overkill

class DataClient:
    def __init__(self,
                 timeseries_url,
                 analytics_url,
                 catalog_url,
                 account_manager_url=None):
        self.timeseries_url = timeseries_url
        self.analytics_url = analytics_url
        self.catalog_url = catalog_url
        self.account_manager_url = account_manager_url or os.environ["ACCOUNT_MANAGER_URL"]
        self.timeout = int(os.environ["DATA_CLIENT_TIMEOUT"])
        self.cache = {}
        self.cache_ttl = int(os.environ["CACHE_TTL"])

        self.temp_alert_threshold = float(os.environ["TEMP_ALERT_THRESHOLD"])
        self.pressure_alert_threshold = float(os.environ["PRESSURE_ALERT_THRESHOLD"])

    def _make_request(self, url, method='GET', params=None, json_data=None, cache_key=None):
        if cache_key and cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached["timestamp"] < self.cache_ttl:
                return cached["data"]

        try:
            if method == 'GET':
                response = requests.get(url, params=params, timeout=self.timeout)
            elif method == 'POST':
                response = requests.post(url, json=json_data, timeout=self.timeout)
            else:
                logger.error(f'Unsupported method: {method}')
                return None

            if response.status_code == 200:
                data = response.json()
                if cache_key:
                    self.cache[cache_key] = {"data": data, "timestamp": time.time()}
                return data
            logger.warning(f'Request failed: {url} - Status: {response.status_code}')
            return None

        except requests.RequestException as e:
            logger.error(f'Request error: {url} - {e}')
            return None
        except Exception:
            return None

    def get_temperature_data(self, pipeline_id, bolt_id=None, limit=100):
        params = {'pipeline_id': pipeline_id, 'limit': limit}
        if bolt_id:
            params['bolt_id'] = bolt_id
        return self._make_request(f'{self.timeseries_url}/temperature', params=params,
                                  cache_key=f'temp_{pipeline_id}_{bolt_id}_{limit}')

    def get_pressure_data(self, pipeline_id, bolt_id=None, limit=100):
        params = {'pipeline_id': pipeline_id, 'limit': limit}
        if bolt_id:
            params['bolt_id'] = bolt_id
        return self._make_request(f'{self.timeseries_url}/pressure', params=params,
                                  cache_key=f'pressure_{pipeline_id}_{bolt_id}_{limit}')

    def get_statistics(self, pipeline_id, bolt_id=None, sensor='temperature', hours=24):
        params = {
            'pipeline_id': pipeline_id,
            'sensor': sensor,
            'hours': hours
        }
        if bolt_id:
            params['bolt_id'] = bolt_id
        return self._make_request(f'{self.analytics_url}/statistics', params=params)

    def get_anomalies(self, pipeline_id=None, hours=24):
        params = {'hours': hours}
        if pipeline_id:
            params['pipeline_id'] = pipeline_id
        return self._make_request(f'{self.timeseries_url}/alerts', params=params)

    def get_pipeline_summary(self, pipeline_id):
        return self._make_request(f'{self.timeseries_url}/summary', params={'pipeline_id': pipeline_id})

    def get_analytics_trends(self, pipeline_id, bolt_id, hours=24):
        params = {'pipeline_id': pipeline_id, 'bolt_id': bolt_id, 'hours': hours}
        return self._make_request(f'{self.analytics_url}/trend', params=params)

    def get_predictions(self, pipeline_id, bolt_id, sensor_type='temperature'):
        params = {
            'pipeline_id': pipeline_id,
            'bolt_id': bolt_id,
            'sensor': sensor_type
        }
        return self._make_request(f'{self.analytics_url}/prediction', params=params)

    def get_risk_assessment(self, pipeline_id, bolt_id):
        return self._make_request(f'{self.analytics_url}/risk', params={'pipeline_id': pipeline_id, 'bolt_id': bolt_id})

    def get_correlations(self, pipeline_id, bolt_id):
        return self._make_request(f'{self.analytics_url}/correlation', params={'pipeline_id': pipeline_id, 'bolt_id': bolt_id})

    def get_pipeline_config(self, pipeline_id):
        return self._make_request(f'{self.catalog_url}/pipelines/{pipeline_id}')

    def get_thresholds(self):
        return self._make_request(f'{self.catalog_url}/config', params={'section': 'thresholds'})

    def get_control_rules(self):
        return self._make_request(f'{self.catalog_url}/config', params={'section': 'rules'})

    def get_service_health(self):
        return self._make_request(f'{self.catalog_url}/services')

    def get_catalog_users(self):
        data = self._make_request(f'{self.catalog_url}/users')
        if data and 'users' in data:
            return data['users']
        return []

    def get_user_chat_id(self, user_name):
        data = self._make_request(f'{self.catalog_url}/users/{user_name}')
        if data and 'user' in data:
            return data['user'].get('chatID')
        return None

    def get_all_chat_ids(self):
        users = self.get_catalog_users()
        seen = set()
        result = []
        for u in users:
            cid = u.get('chatID')
            if cid and cid not in seen:
                seen.add(cid)
                result.append(cid)
        return result

    def get_all_pipelines(self):
        data = self._make_request(f'{self.catalog_url}/pipelines',
                                  cache_key='all_pipelines')
        if data and 'pipelines' in data:
            return list(data['pipelines'].keys())
        return []

    def get_pipeline_live_summary(self, pipeline_id):
        pipeline_config = self.get_pipeline_config(pipeline_id)
        if not pipeline_config or "bolts" not in pipeline_config:
            return None

        bolts = pipeline_config.get("bolts", [])
        bolt_id = bolts[0]["id"] if bolts else None
        if not bolt_id:
            return None

        temp_stats = self.get_statistics(pipeline_id=pipeline_id, bolt_id=bolt_id, sensor="temperature", hours=1)
        pressure_stats = self.get_statistics(pipeline_id=pipeline_id, bolt_id=bolt_id, sensor="pressure", hours=1)

        temp_avg = 0.0
        pressure_avg = 0.0

        if temp_stats and temp_stats.get("statistics"):
            temp_avg = temp_stats["statistics"].get("mean", 0.0)
        if pressure_stats and pressure_stats.get("statistics"):
            pressure_avg = pressure_stats["statistics"].get("mean", 0.0)

        valves = pipeline_config.get("valves", [])
        valve_states = {v["id"]: v.get("current_state", "unknown") for v in valves}

        anomaly_count = 0
        health_score = 100.0
        try:
            risk_data = self._make_request(
                f'{self.analytics_url}/risk',
                params={'pipeline_id': pipeline_id, 'bolt_id': bolt_id},
                cache_key=f'risk_{pipeline_id}'
            )
            if risk_data:
                health_score = risk_data.get('health_score', 100.0)
                risk_assessment = risk_data.get('risk_assessment', {})
                anomaly_count = len(risk_assessment.get('risk_factors', []))
        except Exception:
            pass

        status = "normal"
        if temp_avg > self.temp_alert_threshold or pressure_avg > self.pressure_alert_threshold:
            status = "alert"
        elif temp_avg == 0.0 and pressure_avg == 0.0:
            status = "no_data"

        return {
            "pipeline_id": pipeline_id,
            "temperature_avg": round(temp_avg, 1),
            "pressure_avg": round(pressure_avg, 1),
            "valve_states": valve_states,
            "bolt_count": len(bolts),
            "anomaly_count": anomaly_count,
            "health_score": round(health_score, 1),
            "status": status
        }

    # formatting helpers for telegram messages
    def format_sensor_data(self, data):
        if not data or 'data' not in data:
            return 'No data available'

        readings = data.get('data', [])
        if not readings:
            return 'No recent readings'

        latest = readings[0] if readings else {}
        avg_value = data.get('statistics', {}).get('mean', 0)
        max_value = data.get('statistics', {}).get('max', 0)
        min_value = data.get('statistics', {}).get('min', 0)

        return (f'Latest: {latest.get("value", 0):.2f}\n'
                f'Average: {avg_value:.2f}\n'
                f'Range: {min_value:.2f} - {max_value:.2f}')

    def format_anomalies(self, data):
        if not data or 'alerts' not in data:
            return 'No anomalies detected'

        anomalies = data.get('alerts', [])
        if not anomalies:
            return 'No recent anomalies'

        lines = []
        for anomaly in anomalies[:5]:  # only show 5
            timestamp = datetime.fromtimestamp(anomaly.get('timestamp', 0))
            lines.append(
                f"* {timestamp.strftime('%H:%M')} - {anomaly.get('bolt_id', 'Unknown')} - "
                f"{anomaly.get('anomaly_type', 'Unknown')}"
            )
        return '\n'.join(lines)

    def format_statistics(self, stats):
        if not stats:
            return 'Statistics unavailable'

        lines = [
            f"Mean: {stats.get('mean', 0):.2f}",
            f"Std Dev: {stats.get('std_dev', 0):.2f}",
            f"Min: {stats.get('min', 0):.2f}",
            f"Max: {stats.get('max', 0):.2f}",
            f"Samples: {stats.get('count', 0)}"
        ]
        return '\n'.join(lines)

    def format_risk_assessment(self, risk):
        if not risk:
            return 'Risk assessment unavailable'

        risk_level = risk.get('risk_level', 'Unknown')
        risk_score = risk.get('risk_score', 0)

        indicators = {'low': '[LOW]', 'medium': '[MEDIUM]'}
        indicator = indicators.get(risk_level, '[HIGH]')

        lines = [
            f'{indicator} Risk Level: {risk_level.upper()}',
            f'Score: {risk_score:.1f}/100',
            'Factors:'
        ]

        for factor in risk.get('risk_factors', [])[:3]:
            lines.append(f'  * {factor}')

        return '\n'.join(lines)

    def clear_cache(self):
        self.cache.clear()
        logger.info('data cache cleared')
