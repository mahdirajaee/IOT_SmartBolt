import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from influxdb_client_3 import InfluxDBClient3, Point, WritePrecision, WriteOptions
from urllib.parse import urlparse

from data_models import SensorReading
from banner import print_event

logger = logging.getLogger(__name__)

# north = N pipelines (N1, N2, N3), south = S pipelines (S1, S2, S3)
SECTOR_NORTH = "sector-north"
SECTOR_SOUTH = "sector-south"

class InfluxDB3Storage:
    # influxdb v3 storage - north and south buckets
    # WriteOptions handles batching internally so no manual buffer needed

    _SAFE_ID_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')

    @staticmethod
    def _validate_identifier(value):
        if value is None:
            return None
        val = str(value)
        if not all(c in InfluxDB3Storage._SAFE_ID_CHARS for c in val):
            raise ValueError(f"Invalid identifier: {val}")
        return val

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
            self._ensure_databases()
            self.connected = True
            logger.info(f"Connected to InfluxDB v3 at {self.url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB v3: {e}")
            self.connected = False
            return False

    def _ensure_databases(self):
        failures = []
        for client, bucket in [(self.client_north, self.bucket_north), (self.client_south, self.bucket_south)]:
            try:
                client.query("SELECT 1")
                logger.info(f"Bucket '{bucket}' is ready")
            except Exception as e:
                failures.append(f"{bucket}: {e}")
        if failures:
            raise ConnectionError("; ".join(failures))

    def _get_client_for_sector(self, sector_id):
        if sector_id == SECTOR_SOUTH:
            return self.client_south
        return self.client_north

    def store_sensor_reading(self, reading: SensorReading):
        try:
            points = []
            timestamp = datetime.fromtimestamp(reading.timestamp, tz=timezone.utc)
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

            if self.connected and points:
                parts = []
                if reading.temperature is not None:
                    parts.append(f"T={reading.temperature:.1f}")
                if reading.pressure is not None:
                    parts.append(f"P={reading.pressure:.1f}")
                print_event('STORED', f"{reading.pipeline_id} {' '.join(parts)} sector={sector_id}", 'green')
            elif points:
                print_event('STORE-FAIL', f"{reading.pipeline_id} sector={sector_id} (db error)", 'red')

        except Exception as e:
            logger.error(f"Error storing sensor reading: {e}")
            self.stats["points_failed"] += 1
            print_event('STORE-FAIL', f"{reading.pipeline_id} ({str(e)[:50]})", 'red')

    def _write_points(self, points: List[Point], sector_id: str):
        # client handles batching via WriteOptions, just write directly
        if not points:
            return
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
            self.connected = True
        except Exception as e:
            logger.error(f"Error writing points: {e}")
            self.stats["points_failed"] += len(points)
            self.connected = False

    def query_sensor_data(self, measurement, pipeline_id=None, bolt_id=None,
                         start_time=None, end_time=None, limit=100, sector_id=None):
        try:
            measurement = self._validate_identifier(measurement)
            pipeline_id = self._validate_identifier(pipeline_id)
            bolt_id = self._validate_identifier(bolt_id)

            if not start_time:
                start_time = datetime.utcnow() - timedelta(hours=24)
            if not end_time:
                end_time = datetime.utcnow()

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
                    result: Any = client.query(query)
                    if result:
                        df = result.to_pandas()
                        for _, row in df.iterrows():
                            data.append({
                                "time": row['time'].timestamp() if hasattr(row['time'], 'timestamp') else row['time'],
                                "pipeline_id": row.get('pipeline_id'),
                                "bolt_id": row.get('bolt_id'),
                                measurement: row.get('value')
                            })
                    self.connected = True
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

    def get_pipeline_summary(self, pipeline_id, sector_id=None):
        try:
            pipeline_id = self._validate_identifier(pipeline_id)
            hours = 24
            start_time = datetime.utcnow() - timedelta(hours=hours)

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
                    result: Any = client.query(bolts_query)
                    if result:
                        df = result.to_pandas()
                        for _, row in df.iterrows():
                            bolt_id = row.get('bolt_id')
                            if bolt_id:
                                bolt_ids.add(bolt_id)
                except Exception:
                    continue

            return {
                "pipeline_id": pipeline_id,
                "total_bolts": len(bolt_ids),
                "active_bolts": len(bolt_ids),
                "anomaly_count": 0,
                "time_range_hours": hours
            }

        except Exception as e:
            logger.error(f"Pipeline summary error: {e}")
            return {}

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
