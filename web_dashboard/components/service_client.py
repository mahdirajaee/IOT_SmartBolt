import requests
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ServiceClient:
    def __init__(self):
        self.catalog_url = os.getenv('CATALOG_URL', 'http://localhost:8081')
        self.timeseries_url = os.getenv('TIMESERIES_DB_URL', os.getenv('TIMESERIES_URL', 'http://localhost:8082'))
        self.analytics_url = os.getenv('ANALYTICS_URL', 'http://localhost:8083')
        self.control_center_url = os.getenv('CONTROL_CENTER_URL', 'http://localhost:8085')
        self.account_manager_url = os.getenv('ACCOUNT_MANAGER_URL', 'http://localhost:8084')
        self.timeout = 10
        self.session = requests.Session()

    def _make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        try:
            kwargs['timeout'] = kwargs.get('timeout', self.timeout)
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"{method} request failed for {url}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Failed to parse JSON response from {url}: {e}")
            return None

    def get_pipelines(self) -> List[Dict]:
        response = self._make_request('GET', f"{self.catalog_url}/pipelines")
        if not response:
            return []
        pipelines_map = response.get('pipelines') or {}
        normalized = []
        for pipeline_id, p in pipelines_map.items():
            normalized.append({
                'pipeline_id': pipeline_id,
                'name': p.get('description') or f"Pipeline {pipeline_id}",
                'status': p.get('status', 'unknown'),
                'location': {
                    'sector': p.get('sector_id', 'unknown'),
                    'description': p.get('location', 'Unknown')
                },
                'bolts': p.get('bolts', []),
                'valves': p.get('valves', []),
                'last_update': p.get('last_update')
            })
        return normalized

    def get_pipelines_by_sector(self, sector_id: Optional[str] = None) -> List[Dict]:
        all_pipelines = self.get_pipelines()
        if not sector_id or sector_id == 'all':
            return all_pipelines
        return [p for p in all_pipelines if p.get('location', {}).get('sector') == sector_id]

    def get_pipeline(self, pipeline_id: str) -> Optional[Dict]:
        response = self._make_request('GET', f"{self.catalog_url}/pipelines/{pipeline_id}")
        if not response:
            return None
        pipeline = response.get('pipeline') or {}
        bolts = response.get('bolts') or []
        valves = response.get('valves') or []
        normalized_valves = [{
            'valve_id': v.get('id'),
            'status': v.get('current_state', 'unknown'),
            'location': v.get('location', 'Unknown')
        } for v in valves]
        normalized_bolts = [{
            'bolt_id': b.get('id'),
            'last_temperature': b.get('last_temperature'),
            'last_pressure': b.get('last_pressure'),
            'status': b.get('status', 'unknown')
        } for b in bolts]
        return {
            'pipeline_id': pipeline.get('id', pipeline_id),
            'name': pipeline.get('description') or f"Pipeline {pipeline_id}",
            'status': pipeline.get('status', 'unknown'),
            'location': {
                'sector': pipeline.get('sector_id', 'unknown'),
                'description': pipeline.get('location', 'Unknown')
            },
            'last_update': pipeline.get('last_update'),
            'bolts': normalized_bolts,
            'valves': normalized_valves
        }

    def get_services_status(self) -> List[Dict]:
        response = self._make_request('GET', f"{self.catalog_url}/services")
        if not response:
            return []
        services = response.get('services') or {}
        return list(services.values())

    def get_sensor_data(self, sensor_type: str, pipeline_id: Optional[str] = None, hours: int = 24) -> List[Dict]:
        params: Dict[str, Any] = {'hours': hours}
        if pipeline_id:
            params['pipeline_id'] = pipeline_id

        response = self._make_request('GET', f"{self.timeseries_url}/{sensor_type}", params=params)
        if not response:
            return []
        raw = response.get('data', [])
        result = []
        for item in raw:
            ts = item.get('timestamp') or item.get('time')
            if isinstance(ts, (int, float)):
                timestamp = datetime.fromtimestamp(ts).isoformat()
            else:
                timestamp = ts
            value = item.get(sensor_type, item.get('value'))
            result.append({
                'timestamp': timestamp,
                'value': value,
                'bolt_id': item.get('bolt_id'),
                'pipeline_id': item.get('pipeline_id')
            })
        return result

    def get_statistics(self, pipeline_id: Optional[str] = None, bolt_id: Optional[str] = None, hours: int = 24) -> Dict:
        try:
            result = {'temperature': {}, 'pressure': {}}

            for sensor in ['temperature', 'pressure']:
                if pipeline_id and bolt_id:
                    resp = self._make_request('GET', f"{self.analytics_url}/statistics",
                                              params={'pipeline_id': pipeline_id, 'bolt_id': bolt_id, 'sensor': sensor, 'hours': hours})
                    if resp and resp.get('statistics'):
                        result[sensor] = resp['statistics']
                else:
                    resp = self._make_request('GET', f"{self.analytics_url}/aggregated",
                                              params={'measurement': sensor, 'aggregation': 'mean', 'hours': hours})
                    if resp and resp.get('data'):
                        values = [d.get('value') for d in resp['data'] if d.get('value') is not None]
                        if values:
                            result[sensor] = {'mean': round(sum(values) / len(values), 2), 'count': len(values)}

            return result

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {'temperature': {}, 'pressure': {}}

    def get_alerts(self, pipeline_id: Optional[str] = None, limit: int = 50, bolt_id: Optional[str] = None, severity: Optional[str] = None, hours: int = 24) -> List[Dict]:
        params: Dict[str, Any] = {'limit': limit}
        if pipeline_id:
            params['pipeline_id'] = pipeline_id
        if severity:
            params['severity'] = severity
        resp = self._make_request('GET', f"{self.analytics_url}/alerts", params=params)
        if not resp:
            return []
        alerts = resp.get('alerts', []) or []
        mapped = []
        for a in alerts:
            ts = a.get('timestamp') or a.get('created_at')
            iso_ts = datetime.fromtimestamp(ts).isoformat() if isinstance(ts, (int, float)) else (datetime.now().isoformat() if ts is None else ts)
            value = a.get('temperature') or a.get('pressure') or a.get('value')
            sensor_type = 'temperature' if a.get('temperature') else ('pressure' if a.get('pressure') else a.get('sensor_type'))
            mapped.append({
                'pipeline_id': a.get('pipeline_id'),
                'bolt_id': a.get('bolt_id'),
                'severity': a.get('severity'),
                'anomaly_type': a.get('anomaly_type'),
                'message': a.get('message', ''),
                'value': value,
                'timestamp': iso_ts,
                'sensor_type': sensor_type
            })
        return mapped[:limit]

    def get_predictions(self, pipeline_id: str) -> Dict:
        details = self._make_request('GET', f"{self.catalog_url}/pipelines/{pipeline_id}")
        if not details:
            return {}

        bolts = details.get('bolts') or []
        if not bolts:
            return {}

        bolt_id = bolts[0].get('id')
        predictions_list = []

        for sensor in ['temperature', 'pressure']:
            params = {'pipeline_id': pipeline_id, 'bolt_id': bolt_id, 'sensor': sensor}
            resp = self._make_request('GET', f"{self.analytics_url}/prediction", params=params)
            if resp and resp.get('prediction'):
                pred_data = resp['prediction']
                confidence = pred_data.get('confidence', 0) / 100.0
                method = pred_data.get('method', 'unknown')
                values = pred_data.get('next_values', [])

                predictions_list.append({
                    'type': f'{sensor.title()} Forecast',
                    'description': f'Predicted {sensor} values: {", ".join(f"{v:.1f}" for v in values[:3])}...',
                    'confidence': confidence,
                    'timeframe': 'Next 5 readings'
                })

        return {'predictions': predictions_list}

    def get_pipeline_health(self, pipeline_id: str, bolt_id: Optional[str] = None) -> Dict:
        bid = bolt_id
        if not bid:
            details = self._make_request('GET', f"{self.catalog_url}/pipelines/{pipeline_id}")
            if details:
                bolts = details.get('bolts') or []
                if bolts:
                    bid = bolts[0].get('id')
        if not bid:
            return {}
        params = {'pipeline_id': pipeline_id, 'bolt_id': bid}
        resp = self._make_request('GET', f"{self.analytics_url}/risk", params=params)
        if not resp:
            return {}
        risk = resp.get('risk_assessment') or {}
        score = resp.get('health_score', 0)
        return {
            'health_score': int(score) if isinstance(score, (int, float)) else 0,
            'risk_score': risk.get('risk_score', 0),
            'risk_level': risk.get('risk_level', 'unknown'),
            'risk_factors': risk.get('risk_factors') or [],
        }

    def get_trend(self, pipeline_id: str, bolt_id: Optional[str] = None) -> Dict:
        bid = bolt_id
        if not bid:
            details = self._make_request('GET', f"{self.catalog_url}/pipelines/{pipeline_id}")
            if details:
                bolts = details.get('bolts') or []
                if bolts:
                    bid = bolts[0].get('id')
        if not bid:
            return {}
        resp = self._make_request('GET', f"{self.analytics_url}/trend",
                                  params={'pipeline_id': pipeline_id, 'bolt_id': bid})
        if not resp:
            return {}
        return {
            'temperature': resp.get('temperature_trend') or {},
            'pressure': resp.get('pressure_trend') or {},
        }

    def send_valve_command(self, pipeline_id: str, valve_id: str, command: str, token: str) -> Dict:
        headers = {'Authorization': f'Bearer {token}'}
        body = {
            'pipeline_id': pipeline_id,
            'valve_id': valve_id,
            'action': command,
            'reason': 'Dashboard manual control'
        }
        response = self._make_request('POST', f"{self.control_center_url}/manual", json=body, headers=headers)
        if response:
            return {'success': True, 'data': response}
        return {'success': False, 'error': 'Failed to send command'}

    def get_control_history(self, token: str, limit: int = 100) -> List[Dict]:
        headers = {'Authorization': f'Bearer {token}'}
        response = self._make_request('GET', f"{self.control_center_url}/history", params={'limit': limit}, headers=headers)
        if not response:
            return []
        return response.get('history') or []

    def activate_emergency(self, token: str) -> bool:
        headers = {'Authorization': f'Bearer {token}'}
        response = self._make_request('POST', f"{self.control_center_url}/emergency", json={'action': 'activate'}, headers=headers)
        return bool(response)

    def get_all_users(self, token: str) -> List[Dict]:
        headers = {'Authorization': f'Bearer {token}'}
        response = self._make_request('GET', f"{self.account_manager_url}/users", headers=headers)
        if not response:
            return []
        return response.get('users', [])

    def create_user(self, token: str, user_data: Dict) -> Dict:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = self._make_request('POST', f"{self.account_manager_url}/register",
                                    headers=headers, json=user_data)
        return response or {'error': 'Failed to create user'}

    def update_user(self, token: str, user_id: int, updates: Dict) -> Dict:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = self._make_request('PUT', f"{self.account_manager_url}/users/{user_id}",
                                    headers=headers, json=updates)
        return response or {'error': 'Failed to update user'}

    def delete_user(self, token: str, user_id: int) -> Dict:
        headers = {'Authorization': f'Bearer {token}'}
        response = self._make_request('DELETE', f"{self.account_manager_url}/users/{user_id}",
                                    headers=headers)
        return response or {'error': 'Failed to delete user'}

    def get_user_sectors(self, user_id: int) -> List[str]:
        response = self._make_request('GET', f"{self.catalog_url}/users/{user_id}")
        if not response or 'user' not in response:
            return []
        sectors = response.get('user', {}).get('sectors', [])
        return [s.get('sectorID') for s in sectors if s.get('sectorID')]

    def get_sector_options_for_user(self, user_id: int, role: str) -> List[Dict]:
        sector_labels = {
            'sector-north': 'North Sector',
            'sector-south': 'South Sector'
        }
        if role == 'admin':
            options = [{'label': 'All Sectors', 'value': 'all'}]
            options.extend([{'label': v, 'value': k} for k, v in sector_labels.items()])
            return options
        user_sectors = self.get_user_sectors(user_id)
        if not user_sectors:
            return [{'label': 'No sectors assigned', 'value': '', 'disabled': True}]
        options = []
        if len(user_sectors) > 1:
            options.append({'label': 'All My Sectors', 'value': 'all'})
        for sector_id in user_sectors:
            label = sector_labels.get(sector_id, sector_id)
            options.append({'label': label, 'value': sector_id})
        return options

    def get_all_pipeline_bundles(self, token: str) -> Dict:
        headers = {'Authorization': f'Bearer {token}'}
        response = self._make_request('GET', f"{self.catalog_url}/pipelines", headers=headers)
        if not response:
            return {}
        return response.get('pipeline_bundles', {})

    def create_pipeline_bundle(self, token: str, bundle_data: Dict) -> Dict:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = self._make_request('POST', f"{self.catalog_url}/pipelines",
                                    headers=headers, json=bundle_data)
        return response or {'error': 'Failed to create pipeline bundle'}

    def update_pipeline_bundle(self, token: str, pipeline_id: str, updates: Dict) -> Dict:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = self._make_request('PUT', f"{self.catalog_url}/pipelines/{pipeline_id}",
                                    headers=headers, json=updates)
        return response or {'error': 'Failed to update pipeline bundle'}

    def delete_pipeline_bundle(self, token: str, pipeline_id: str) -> Dict:
        headers = {'Authorization': f'Bearer {token}'}
        response = self._make_request('DELETE', f"{self.catalog_url}/pipelines/{pipeline_id}",
                                    headers=headers)
        return response or {'error': 'Failed to delete pipeline bundle'}

