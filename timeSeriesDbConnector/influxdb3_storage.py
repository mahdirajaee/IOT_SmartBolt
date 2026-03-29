import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from influxdb_client_3 import InfluxDBClient3, Point, WritePrecision, WriteOptions
from urllib.parse import urlparse

from data_models import (
    SensorReading, ValveStatus, AnomalyEvent,
    Statistics, AggregationType
)

logger = logging.getLogger(__name__)

# north = N pipelines (N1, N2, N3), south = S pipelines (S1, S2, S3)
SECTOR_NORTH = "sector-north"
SECTOR_SOUTH = "sector-south"

class InfluxDB3Storage:
    # influxdb v3 storage - north and south buckets
    # WriteOptions handles batching internally so no manual buffer needed

    def __init__(self, url, bucket_north, bucket_south, token=None, org=None):
        cleaned_url = url.strip() or "http://localhost:8086"
        parsed_url = urlparse(cleaned_url)
        if not parsed_url.scheme:
            cleaned_url = f"http://{cleaned_url}"
        self.url = cleaned_url.rstrip("/")
        self.bucket_north = bucket_north
        self.bucket_south = bucket_south
        self.token = token
        self.org = org

        self.flight_options = {"disable_server_verification": True} if cleaned_url.startswith("http://") else None

        self.client_north = None
        self.client_south = None
        self.connected = False

        self.stats = {
            "points_written": 0,
            "points_failed": 0,
            "queries_executed": 0,
            "queries_failed": 0,
            "by_measurement": {},
            "by_sector": {SECTOR_NORTH: 0, SECTOR_SOUTH: 0}
        }

        self._connect()

    def _connect(self) -> bool:
        try:
            self.client_north = InfluxDBClient3(
                host=self.url,
                org=self.org,
                database=self.bucket_north,
                token=self.token,
                write_options=WriteOptions(batch_size=100, flush_interval=5000),
                flight_client_options=self.flight_options
            )
            self.client_south = InfluxDBClient3(
                host=self.url,
                org=self.org,
                database=self.bucket_south,
                token=self.token,
                write_options=WriteOptions(batch_size=100, flush_interval=5000),
                flight_client_options=self.flight_options
            )
            self._ensure_databases()
            self.connected = True
            logger.info(f"Connected to InfluxDB v3 at {self.url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB v3: {e}")
            self.connected = False
            return False

    def _ensure_databases(self):
        for client, bucket in [(self.client_north, self.bucket_north), (self.client_south, self.bucket_south)]:
            try:
                test_point = Point("test") \
                    .field("value", 1) \
                    .time(datetime.now(), WritePrecision.NS)
                client.write(test_point)
                logger.info(f"Bucket '{bucket}' is ready")
            except Exception as e:
                logger.warning(f"Bucket '{bucket}' initialization: {e}")

    def _get_client_for_sector(self, sector_id):
        if sector_id == SECTOR_SOUTH:
            return self.client_south
        return self.client_north

    def store_sensor_reading(self, reading: SensorReading): # reading is a dataclass with pipeline_id, bolt_id, timestamp, temperature, pressure, sector_id 
        try:
            points = []
            timestamp = datetime.fromtimestamp(reading.timestamp) # how hndle the SECTOR_SOUTH?
            sector_id = reading.sector_id or SECTOR_NORTH   

            if reading.temperature is not None:
                temp_point = Point("temperature") \
                    .tag("pipeline_id", reading.pipeline_id) \
                    .tag("bolt_id", reading.bolt_id) \
                    .tag("sector_id", sector_id) \
                    .field("value", float(reading.temperature)) \
                    .time(timestamp, WritePrecision.NS)
                points.append(temp_point)

            if reading.pressure is not None:
                pressure_point = Point("pressure") \
                    .tag("pipeline_id", reading.pipeline_id) \
                    .tag("bolt_id", reading.bolt_id) \
                    .tag("sector_id", sector_id) \
                    .field("value", float(reading.pressure)) \
                    .time(timestamp, WritePrecision.NS)
                points.append(pressure_point)

            self._write_points(points, sector_id)

        except Exception as e:
            logger.error(f"Error storing sensor reading: {e}")
            self.stats["points_failed"] += 1

    def store_valve_status(self, status: ValveStatus):
        try:
            timestamp = datetime.fromtimestamp(status.timestamp)
            sector_id = status.sector_id or SECTOR_NORTH
            state_value = str(status.state) if isinstance(status.state, dict) else status.state
            point = Point("valve_status") \
                .tag("pipeline_id", status.pipeline_id) \
                .tag("valve_id", status.valve_id) \
                .tag("sector_id", sector_id) \
                .field("state", state_value) \
                .time(timestamp, WritePrecision.NS)

            self._write_points([point], sector_id)

        except Exception as e:
            logger.error(f"Error storing valve status: {e}")
            self.stats["points_failed"] += 1

    def store_anomaly_event(self, event: AnomalyEvent):
        try:
            timestamp = datetime.fromtimestamp(event.timestamp)
            sector_id = event.sector_id or SECTOR_NORTH
            point = Point("anomalies") \
                .tag("pipeline_id", event.pipeline_id) \
                .tag("bolt_id", event.bolt_id) \
                .tag("sector_id", sector_id) \
                .tag("anomaly_type", event.anomaly_type) \
                .tag("severity", event.severity) \
                .field("description", event.description) \
                .field("temperature", event.sensor_values.get("temperature", 0)) \
                .field("pressure", event.sensor_values.get("pressure", 0)) \
                .time(timestamp, WritePrecision.NS)

            self._write_points([point], sector_id)

        except Exception as e:
            logger.error(f"Error storing anomaly event: {e}")
            self.stats["points_failed"] += 1

    def _write_points(self, points: List[Point], sector_id: str):
        # client handles batching via WriteOptions, just write directly
        try:
            client = self._get_client_for_sector(sector_id)
            for point in points:
                client.write(point)
                measurement = point._name if hasattr(point, '_name') else 'unknown'
                self.stats["by_measurement"].setdefault(measurement, 0)
                self.stats["by_measurement"][measurement] += 1
            self.stats["points_written"] += len(points)
            self.stats["by_sector"].setdefault(sector_id, 0)
            self.stats["by_sector"][sector_id] += len(points)
        except Exception as e:
            logger.error(f"Error writing points: {e}")
            self.stats["points_failed"] += len(points)

    def query_sensor_data(self, measurement, pipeline_id=None, bolt_id=None,
                         start_time=None, end_time=None, limit=100, sector_id=None):
        # TODO: handle query timeouts better
        try:
            if not start_time:
                start_time = datetime.now() - timedelta(hours=24)
            if not end_time:
                end_time = datetime.now()

            query = f"""
                SELECT time, pipeline_id, bolt_id, value
                FROM {measurement}
                WHERE time >= '{start_time.isoformat()}Z'
                AND time <= '{end_time.isoformat()}Z'
            """

            if pipeline_id:
                query += f" AND pipeline_id = '{pipeline_id}'"
            if bolt_id:
                query += f" AND bolt_id = '{bolt_id}'"

            query += f" ORDER BY time DESC LIMIT {limit}"

            clients_to_query = self._get_clients_for_query(sector_id)

            data = []
            for client in clients_to_query:
                try:
                    result = client.query(query)
                    if result:
                        df = result.to_pandas()
                        for _, row in df.iterrows():
                            data.append({
                                "time": row['time'].timestamp() if hasattr(row['time'], 'timestamp') else row['time'],
                                "pipeline_id": row.get('pipeline_id'),
                                "bolt_id": row.get('bolt_id'),
                                measurement: row.get('value')
                            })
                except Exception as e:
                    logger.error(f"Query error on bucket: {e}")

            self.stats["queries_executed"] += 1
            return data[:limit]

        except Exception as e:
            logger.error(f"Query error: {e}")
            self.stats["queries_failed"] += 1
            return []

    def _get_clients_for_query(self, sector_id: Optional[str] = None) -> List[InfluxDBClient3]:
        if sector_id == SECTOR_NORTH:
            return [self.client_north]
        elif sector_id == SECTOR_SOUTH:
            return [self.client_south]
        return [self.client_north, self.client_south]

    def query_statistics(self,
                        measurement: str,
                        pipeline_id: str,
                        bolt_id: str,
                        hours: int = 24,
                        sector_id: Optional[str] = None) -> Optional[Statistics]:
        try:
            start_time = datetime.now() - timedelta(hours=hours)

            query = f"""
                SELECT
                    AVG(value) as mean_value,
                    MIN(value) as min_value,
                    MAX(value) as max_value,
                    STDDEV(value) as stddev_value,
                    COUNT(value) as count_value
                FROM {measurement}
                WHERE time >= '{start_time.isoformat()}Z'
                AND pipeline_id = '{pipeline_id}'
                AND bolt_id = '{bolt_id}'
            """

            last_query = f"""
                SELECT time, value
                FROM {measurement}
                WHERE pipeline_id = '{pipeline_id}'
                AND bolt_id = '{bolt_id}'
                ORDER BY time DESC
                LIMIT 1
            """

            clients = self._get_clients_for_query(sector_id)

            stats_row = None
            last_row = None

            for client in clients:
                try:
                    result = client.query(query)
                    if result:
                        df = result.to_pandas()
                        if not df.empty and df.iloc[0].get('count_value', 0) > 0:
                            stats_row = df.iloc[0]
                            break
                except Exception:
                    continue

            for client in clients:
                try:
                    last_result = client.query(last_query)
                    if last_result:
                        df_last = last_result.to_pandas()
                        if not df_last.empty:
                            last_row = df_last.iloc[0]
                            break
                except Exception:
                    continue

            if stats_row is None or stats_row.get('count_value', 0) == 0:
                return None

            return Statistics(
                mean=stats_row.get('mean_value', 0),
                min=stats_row.get('min_value', 0),
                max=stats_row.get('max_value', 0),
                stddev=stats_row.get('stddev_value', 0),
                count=stats_row.get('count_value', 0),
                last_value=last_row['value'] if last_row is not None else 0,
                last_timestamp=last_row['time'].timestamp() if last_row is not None and hasattr(last_row['time'], 'timestamp') else None
            )

        except Exception as e:
            logger.error(f"Statistics query error: {e}")
            return None

    def query_aggregated_data(self, measurement, aggregation, window="1h",
                             pipeline_id=None, start_time=None, sector_id=None):
        # this query is slow sometimes
        try:
            if not start_time:
                start_time = datetime.now() - timedelta(days=1)

            fn_map = {
                AggregationType.MEAN: "AVG",
                AggregationType.MAX: "MAX",
                AggregationType.MIN: "MIN",
                AggregationType.COUNT: "COUNT",
                AggregationType.STDDEV: "STDDEV",
                AggregationType.LAST: "LAST",
                AggregationType.FIRST: "FIRST"
            }

            fn = fn_map.get(aggregation, "AVG")
            interval = window.replace('h', ' HOUR').replace('m', ' MINUTE').replace('s', ' SECOND')

            query = f"""
                SELECT
                    DATE_BIN(INTERVAL '{interval}', time) as window_time,
                    pipeline_id,
                    bolt_id,
                    {fn}(value) as agg_value
                FROM {measurement}
                WHERE time >= '{start_time.isoformat()}Z'
            """

            if pipeline_id:
                query += f" AND pipeline_id = '{pipeline_id}'"

            query += " GROUP BY window_time, pipeline_id, bolt_id ORDER BY window_time"

            clients = self._get_clients_for_query(sector_id)

            data = []
            for client in clients:
                try:
                    result = client.query(query)
                    if result:
                        df = result.to_pandas()
                        for _, row in df.iterrows():
                            data.append({
                                "time": row['window_time'].timestamp() if hasattr(row.get('window_time'), 'timestamp') else row.get('window_time'),
                                "value": row.get('agg_value'),
                                "pipeline_id": row.get('pipeline_id'),
                                "bolt_id": row.get('bolt_id')
                            })
                except Exception as e:
                    logger.error(f"Aggregation query error on bucket: {e}")

            return data

        except Exception as e:
            logger.error(f"Aggregation query error: {e}")
            return []

    def get_pipeline_summary(self, pipeline_id, sector_id=None):
        try:
            hours = 24
            start_time = datetime.now() - timedelta(hours=hours)

            bolts_query = f"""
                SELECT DISTINCT bolt_id
                FROM (
                    SELECT bolt_id FROM temperature WHERE pipeline_id = '{pipeline_id}' AND time >= '{start_time.isoformat()}Z'
                    UNION
                    SELECT bolt_id FROM pressure WHERE pipeline_id = '{pipeline_id}' AND time >= '{start_time.isoformat()}Z'
                )
            """

            clients = self._get_clients_for_query(sector_id)

            bolt_ids = set()
            for client in clients:
                try:
                    result = client.query(bolts_query)
                    if result:
                        df = result.to_pandas()
                        for _, row in df.iterrows():
                            bolt_id = row.get('bolt_id')
                            if bolt_id:
                                bolt_ids.add(bolt_id)
                except Exception:
                    continue

            anomaly_query = f"""
                SELECT COUNT(*) as count
                FROM anomalies
                WHERE pipeline_id = '{pipeline_id}'
                AND time >= '{start_time.isoformat()}Z'
            """

            anomaly_count = 0
            for client in clients:
                try:
                    anomaly_result = client.query(anomaly_query)
                    if anomaly_result:
                        df_anomaly = anomaly_result.to_pandas()
                        if not df_anomaly.empty:
                            anomaly_count += df_anomaly.iloc[0].get('count', 0)
                except Exception:
                    continue

            return {
                "pipeline_id": pipeline_id,
                "total_bolts": len(bolt_ids),
                "active_bolts": len(bolt_ids),
                "anomaly_count": anomaly_count,
                "time_range_hours": hours
            }

        except Exception as e:
            logger.error(f"Pipeline summary error: {e}")
            return {}

    def query_alerts(self, pipeline_id=None, severity=None, hours=24,
                    limit=100, sector_id=None):
        try:
            start_time = datetime.now() - timedelta(hours=hours)

            query = f"""
                SELECT time, pipeline_id, bolt_id, sector_id, anomaly_type, severity, description, temperature, pressure
                FROM anomalies
                WHERE time >= '{start_time.isoformat()}Z'
            """

            if pipeline_id:
                query += f" AND pipeline_id = '{pipeline_id}'"
            if severity:
                query += f" AND severity = '{severity}'"

            query += f" ORDER BY time DESC LIMIT {limit}"

            clients = self._get_clients_for_query(sector_id)

            data = []
            for client in clients:
                try:
                    result = client.query(query)
                    if result:
                        df = result.to_pandas()
                        for _, row in df.iterrows():
                            data.append({
                                "timestamp": row['time'].timestamp() if hasattr(row['time'], 'timestamp') else row['time'],
                                "pipeline_id": row.get('pipeline_id'),
                                "bolt_id": row.get('bolt_id'),
                                "sector_id": row.get('sector_id'),
                                "anomaly_type": row.get('anomaly_type'),
                                "severity": row.get('severity'),
                                "message": row.get('description', ''),
                                "temperature": row.get('temperature'),
                                "pressure": row.get('pressure')
                            })
                except Exception as e:
                    logger.error(f"Query alerts error on bucket: {e}")

            self.stats["queries_executed"] += 1
            data.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return data[:limit]

        except Exception as e:
            logger.error(f"Query alerts error: {e}")
            self.stats["queries_failed"] += 1
            return []

    def close(self):
        try:
            if self.client_north:
                self.client_north.close()
            if self.client_south:
                self.client_south.close()
            logger.info("InfluxDB v3 connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

    def get_stats(self):
        return self.stats.copy()
