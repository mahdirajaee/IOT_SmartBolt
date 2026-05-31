import os, time, threading, logging
from typing import Dict, Any, List, Optional
from collections import deque, Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class PipelineStatus:
    pipeline_id: str
    last_update: float
    temperature_avg: float = 0.0
    pressure_avg: float = 0.0
    valve_states: Dict[str, str] = field(default_factory=dict)
    bolt_count: int = 0
    anomaly_count: int = 0
    health_score: float = 100.0

@dataclass
class ServiceStatus:
    name: str
    status: str
    last_check: float
    endpoint: str
    port: int

class ServiceStateManager:
    def __init__(self, data_client=None):
        self.pipelines: Dict[str, PipelineStatus] = {}
        self.services: Dict[str, ServiceStatus] = {}
        self.alerts_history = deque(maxlen=100)  # 100 alerts should be enough for anyone
        self.commands_history = deque(maxlen=50)  # 50 commands history, increase if needed
        self.statistics_cache = {}
        self.cache_ttl = int(os.environ["STATS_CACHE_TTL"])
        self.lock = threading.RLock()
        self.data_client = data_client

        self._initialize_pipelines()
        self._initialize_services()

    def _initialize_pipelines(self):
        # old way - was fetching from catalog every time
        # pipeline_ids = self._fetch_from_catalog()
        pipeline_ids = []
        if self.data_client:
            pipeline_ids = self.data_client.get_all_pipelines()

        if not pipeline_ids:
            pipeline_ids = []

        for pipeline_id in pipeline_ids:
            self.pipelines[pipeline_id] = PipelineStatus(
                pipeline_id=pipeline_id,
                last_update=time.time(),
                valve_states={f'valve{pipeline_id}001': 'open'}
            )
        logger.info(f'Initialized {len(pipeline_ids)} pipelines')
    
    def _initialize_services(self):
        # hardcoded service list, could read from catalog but this is simpler
        services_config = [
            ('catalog', 'http://localhost:8081', 8081),
            ('timeseries_db', 'http://localhost:8082', 8082),
            ('analytics', 'http://localhost:8083', 8083),
            ('account_manager', 'http://localhost:8084', 8084),
            ('control_center', 'http://localhost:8085', 8085),
            ('raspberry_pi_north', 'http://localhost:8086', 8086),
            ('raspberry_pi_south', 'http://localhost:8088', 8088)
        ]

        for name, endpoint, port in services_config:
            self.services[name] = ServiceStatus(
                name=name,
                status='unknown',
                last_check=0,
                endpoint=endpoint,
                port=port
            )
        logger.info('Initialized service states')
    
    def update_pipeline_status(self, pipeline_id, data):
        with self.lock:
            if pipeline_id not in self.pipelines:
                self.pipelines[pipeline_id] = PipelineStatus(
                    pipeline_id=pipeline_id,
                    last_update=time.time()
                )

            pipeline = self.pipelines[pipeline_id]
            pipeline.last_update = time.time()

            if 'bolt_data' in data:
                temps = []
                pressures = []
                for bolt_id, readings in data['bolt_data'].items():
                    if 'temperature' in readings:
                        temps.append(readings['temperature'])
                    if 'pressure' in readings:
                        pressures.append(readings['pressure'])

                if temps:
                    pipeline.temperature_avg = sum(temps) / len(temps)
                if pressures:
                    pipeline.pressure_avg = sum(pressures) / len(pressures)
                pipeline.bolt_count = len(data['bolt_data'])

            if 'valve_status' in data:
                pipeline.valve_states.update(data['valve_status'])
            if 'anomaly_count' in data:
                pipeline.anomaly_count = data['anomaly_count']
            if 'health_score' in data:
                pipeline.health_score = data['health_score']

            logger.debug(f'Updated status for pipeline {pipeline_id}')
    
    def add_alert(self, alert):
        with self.lock:
            alert_record = {
                'timestamp': alert.get('timestamp', time.time()),
                'type': alert.get('alert_type', 'unknown'),
                'pipeline_id': alert.get('pipeline_id', 'unknown'),
                'severity': alert.get('severity', 'info'),
                'message': alert.get('message', ''),
                'acknowledged': False
            }

            self.alerts_history.append(alert_record)

            pipeline_id = alert.get('pipeline_id')
            if pipeline_id and pipeline_id in self.pipelines:
                self.pipelines[pipeline_id].anomaly_count += 1

            logger.debug(f"Added alert: {alert_record['type']} for {alert_record['pipeline_id']}")
    
    def add_command(self, command):
        with self.lock:
            command_record = {
                'timestamp': command.get('timestamp', time.time()),
                'pipeline_id': command.get('pipeline_id', 'unknown'),
                'valve_id': command.get('valve_id', 'unknown'),
                'action': command.get('command', 'unknown'),
                'user_id': command.get('user_id', 'system'),
                'status': 'sent'
            }
            self.commands_history.append(command_record)
            logger.debug(f"Added command: {command_record['action']} for {command_record['valve_id']}")
    
    def update_service_status(self, service_name, status):
       with self.lock:
           if service_name in self.services:
               self.services[service_name].status = status
               self.services[service_name].last_check = time.time()
               logger.debug(f'Updated service {service_name} status to {status}')
               return
           for registered_name in self.services:
              if registered_name in service_name:
                  self.services[registered_name].status = status
                  self.services[registered_name].last_check = time.time()
                  logger.debug(f'Updated service {registered_name} status to {status} (matched from {service_name})')
                  return
    def get_pipeline_summary(self, pipeline_id=None):
        with self.lock:
            if pipeline_id:
                if pipeline_id in self.pipelines:
                    pipeline = self.pipelines[pipeline_id]
                    return {
                        'pipeline_id': pipeline.pipeline_id,
                        'last_update': pipeline.last_update,
                        'temperature_avg': round(pipeline.temperature_avg, 2),
                        'pressure_avg': round(pipeline.pressure_avg, 2),
                        'valve_states': pipeline.valve_states,
                        'bolt_count': pipeline.bolt_count,
                        'anomaly_count': pipeline.anomaly_count,
                        'health_score': round(pipeline.health_score, 2),
                        'status': self._determine_pipeline_status(pipeline)
                    }
                return None

            summaries = {}
            for pid, pipeline in self.pipelines.items():
                summaries[pid] = {
                    'temperature_avg': round(pipeline.temperature_avg, 2),
                    'pressure_avg': round(pipeline.pressure_avg, 2),
                    'anomaly_count': pipeline.anomaly_count,
                    'health_score': round(pipeline.health_score, 2),
                    'status': self._determine_pipeline_status(pipeline)
                }
            return summaries
    
    def _determine_pipeline_status(self, pipeline):
        # thresholds are kinda arbitrary, adjust based on actual data
        if time.time() - pipeline.last_update > 300:
            return 'offline'
        elif pipeline.health_score < 40:
            return 'critical'
        elif pipeline.anomaly_count > 5:
            return 'warning'
        elif pipeline.temperature_avg > 45 or pipeline.pressure_avg > 120:
            return 'alert'
        return 'normal'
    
    def get_recent_alerts(self, limit=10, pipeline_id=None):
        with self.lock:
            alerts = list(self.alerts_history)
            if pipeline_id:
                alerts = [a for a in alerts if a['pipeline_id'] == pipeline_id]
            alerts.sort(key=lambda x: x['timestamp'], reverse=True)
            return alerts[:limit]

    def get_recent_commands(self, limit=10):
        with self.lock:
            commands = list(self.commands_history)
            commands.sort(key=lambda x: x['timestamp'], reverse=True)
            return commands[:limit]
    
    def acknowledge_alert(self, alert_index):
        with self.lock:
            if 0 <= alert_index < len(self.alerts_history):
                self.alerts_history[alert_index]['acknowledged'] = True
                return True
            return False

    def get_service_health(self):
        with self.lock:
            health = {}
            for name, service in self.services.items():
                health[name] = {
                    'status': service.status,
                    'last_check': service.last_check,
                    'online': service.status == 'healthy'
                }
            return health
    
    def get_statistics(self, hours=24):
        cache_key = f'stats_{hours}'

        if cache_key in self.statistics_cache:
            cached = self.statistics_cache[cache_key]
            if time.time() - cached['cached_at'] < self.cache_ttl:
                return cached['data']

        with self.lock:
            cutoff_time = time.time() - (hours * 3600)

            recent_alerts = [a for a in self.alerts_history if a['timestamp'] > cutoff_time]
            recent_commands = [c for c in self.commands_history if c['timestamp'] > cutoff_time]

            alert_by_type = Counter(a['type'] for a in recent_alerts)
            alert_by_severity = Counter(a['severity'] for a in recent_alerts)

            stats = {
                'time_range_hours': hours,
                'total_alerts': len(recent_alerts),
                'total_commands': len(recent_commands),
                'alerts_by_type': alert_by_type,
                'alerts_by_severity': alert_by_severity,
                'pipelines_status': {
                    pid: self._determine_pipeline_status(p)
                    for pid, p in self.pipelines.items()
                },
                'services_online': sum(1 for s in self.services.values() if s.status == 'healthy'),
                'timestamp': time.time()
            }

            self.statistics_cache[cache_key] = {
                'data': stats,
                'cached_at': time.time()
            }
            return stats
    
    def clear_old_data(self, days=7):
        # 86400 = seconds in a day
        with self.lock:
            cutoff_time = time.time() - (days * 86400)

            self.alerts_history = deque(
                [a for a in self.alerts_history if a['timestamp'] > cutoff_time],
                maxlen=100
            )
            self.commands_history = deque(
                [c for c in self.commands_history if c['timestamp'] > cutoff_time],
                maxlen=50
            )
            logger.info(f'Cleared data older than {days} days')

    def reset_statistics(self):
        with self.lock:
            self.statistics_cache.clear()
            for pipeline in self.pipelines.values():
                pipeline.anomaly_count = 0
                pipeline.health_score = 100.0
            logger.info('Stats reset')