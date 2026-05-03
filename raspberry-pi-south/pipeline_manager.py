import os
import json
import threading
import logging
import requests
import time
from typing import Dict, List, Tuple, Any, Callable
from dotenv import load_dotenv
from data_generator import Pipeline, SensorLimits

logger = logging.getLogger(__name__)

class PipelineManager:

    def __init__(self):
        self.config_lock = threading.RLock()
        self.pipelines: Dict[str, Pipeline] = {}
        self.observers = []
        self.observers:list[Callable]
        self.sensor_limits = None
        self.sector_id = os.getenv("SECTOR_ID", "sector-unknown")
        self.catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
        self.sync_interval = int(os.getenv("CATALOG_SYNC_INTERVAL", 45))  # slower network here
        self.last_sync_time = 0
        self.sync_thread = None
        self.sync_running = False
        self.current_publish_interval = int(os.getenv("PUBLISH_INTERVAL", 5))
        self._load_configuration()
        self._start_catalog_sync()
        logger.info(f"PipelineManager initialized for sector: {self.sector_id}")

    @staticmethod
    def _generate_default_bolt_id(pid):
        return f"bolt_{pid.lower()}"

    def _load_configuration(self):
        load_dotenv(override=True)

        self.sensor_limits = SensorLimits(
            temp_min=float(os.getenv("TEMP_MIN", 20.0)),
            temp_max=float(os.getenv("TEMP_MAX", 50.0)),
            pressure_min=float(os.getenv("PRESSURE_MIN", 80.0)),
            pressure_max=float(os.getenv("PRESSURE_MAX", 120.0))
        )

        logger.info(f"Sensor limits loaded: temp [{self.sensor_limits.temp_min}-{self.sensor_limits.temp_max}], "
                   f"pressure [{self.sensor_limits.pressure_min}-{self.sensor_limits.pressure_max}]")
        logger.info("Pipelines will be discovered dynamically from Catalog")
    
    def get_pipeline(self, pid):
        with self.config_lock:
            return self.pipelines.get(pid)
    
    def get_all_pipelines(self):
        with self.config_lock:
            return self.pipelines.copy()

    def get_pipeline_config(self):
        with self.config_lock:
            config = {}
            for pid, pipeline in self.pipelines.items():
                config[pid] = {
                    "status": pipeline.status,
                    "sensors": [(bid, "temperature,pressure") for bid in pipeline.bolts.keys()],
                    "valves": [(vid, valve.state) for vid, valve in pipeline.valves.items()],
                    "data_points": pipeline.data_points_generated
                }
            return config
    
    def add_pipeline(self, pid, sensors, valves):
        with self.config_lock:
            if pid in self.pipelines:
                logger.warning(f"Pipeline {pid} exists")
                return False

            pipeline = Pipeline(pid)

            bolt_ids = set()
            for sensor_id, sensor_type in sensors:
                bolt_ids.add(sensor_id)

            for bolt_id in bolt_ids:
                pipeline.add_bolt(bolt_id, self.sensor_limits)

            for valve_id, valve_state in valves:
                pipeline.add_valve(valve_id, valve_state)

            self.pipelines[pid] = pipeline
            logger.info(f"Added pipeline {pid}")
        
        self._notify_observers()
        return True
    
    def remove_pipeline(self, pid):
        with self.config_lock:
            if pid in self.pipelines:
                del self.pipelines[pid]
                logger.info(f"Removed {pid}")
                self._notify_observers()
                return True
            return False
    
    def update_pipeline_status(self, pid, status):
        with self.config_lock:
            if pid in self.pipelines:
                self.pipelines[pid].status = status
                logger.info(f"Updated {pid} to {status}")
                self._notify_observers()
                return True
            return False
    
    def set_valve_state(self, pid, valve_id, state):
        pipeline = self.get_pipeline(pid)
        if pipeline:
            return pipeline.set_valve_state(valve_id, state)
        return False
    
    def get_all_bolts(self):
        bolts = []
        with self.config_lock:
            for pid, pipeline in self.pipelines.items():
                for bolt_id, bolt in pipeline.bolts.items():
                    bolts.append({
                        "bolt_id": bolt_id,
                        "pipeline_id": pid,
                        "temperature": bolt.temperature,
                        "pressure": bolt.pressure,
                    })
        return bolts
    
    def get_all_valves(self):
        valves = []
        with self.config_lock:
            for pid, pipeline in self.pipelines.items():
                for valve_id, valve in pipeline.valves.items():
                    valves.append({
                        "valve_id": valve_id,
                        "pipeline_id": pid,
                        **valve.get_status()
                    })
        return valves
    
    def add_observer(self, cb):
        self.observers.append(cb)

    def remove_observer(self, cb):
        if cb in self.observers:
            self.observers.remove(cb)

    def _notify_observers(self):
        config = self.get_pipeline_config()
        for callback in self.observers:
            try:
                callback(config)
            except Exception as e:
                logger.error(f"Error notifying observer {callback.__name__}: {e}")
    
    def reload_configuration(self):
        self._load_configuration()

    def get_statistics(self):
        with self.config_lock:
            total_bolts = sum(len(p.bolts) for p in self.pipelines.values())
            total_valves = sum(len(p.valves) for p in self.pipelines.values())
            total_data_points = sum(p.data_points_generated for p in self.pipelines.values())
            
            return {
                "pipeline_count": len(self.pipelines),
                "total_bolts": total_bolts,
                "total_valves": total_valves,
                "total_data_points": total_data_points,
                "active_pipelines": sum(1 for p in self.pipelines.values() if p.status == "active")
            }
    
    def _start_catalog_sync(self):
        if not self.sync_running:
            self.sync_running = True
            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()
            logger.info("Started catalog sync thread")

    def _sync_loop(self):
        while self.sync_running:
            try:
                current_time = time.time()
                if current_time - self.last_sync_time >= self.sync_interval:
                    self.sync_with_catalog()
                    self.last_sync_time = current_time
                time.sleep(5)  
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                time.sleep(10)  

    def sync_with_catalog(self):
        try:
            cfg_resp = requests.get(
                f"{self.catalog_url}/config",
                params={"section": "global"}, timeout=5
            )
            if cfg_resp.status_code == 200:
                global_cfg = cfg_resp.json().get("global_config", {})
                new_interval = global_cfg.get("publish_interval")
                if new_interval and new_interval != self.current_publish_interval:
                    self.current_publish_interval = new_interval
                    logger.info(f"Updated publish interval from catalog: {new_interval}s")
        except Exception as e:
            logger.debug(f"Could not fetch config from catalog: {e}")

        try:
            response = requests.get(f"{self.catalog_url}/pipelines", timeout=10)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch pipelines from catalog: {response.status_code}")
                return False

            catalog_data = response.json()
            catalog_pipelines = catalog_data.get("pipelines", {})

            new_pipelines_added = False
            sector_pipeline_count = 0

            for pipeline_id, pipeline_info in catalog_pipelines.items():
                pipeline_sector = pipeline_info.get("sector_id", "sector-unknown")

                if pipeline_sector != self.sector_id:
                    continue

                sector_pipeline_count += 1

                if pipeline_id not in self.pipelines:
                    logger.info(f"Found new pipeline in catalog for {self.sector_id}: {pipeline_id}")

                    detail_response = requests.get(
                        f"{self.catalog_url}/pipelines/{pipeline_id}",
                        timeout=10
                    )

                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        self._add_pipeline_from_catalog(pipeline_id, detail_data)
                        new_pipelines_added = True
                    else:
                        logger.warning(f"Failed to get details for pipeline {pipeline_id}")

            catalog_pipeline_ids = {
                pid for pid, info in catalog_pipelines.items()
                if info.get("sector_id", "sector-unknown") == self.sector_id
            }
            local_pipeline_ids = set(self.pipelines.keys())
            removed_ids = local_pipeline_ids - catalog_pipeline_ids

            for pipeline_id in removed_ids:
                logger.info(f"Pipeline {pipeline_id} no longer in catalog, removing")
                self.remove_pipeline(pipeline_id)

            logger.debug(f"Sector {self.sector_id} has {sector_pipeline_count} pipelines in catalog, "
                        f"{len(self.pipelines)} currently loaded")

            if new_pipelines_added or removed_ids:
                self._notify_observers()
                logger.info(f"Pipeline sync completed for {self.sector_id}: +{int(new_pipelines_added)} -{len(removed_ids)}")

            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync with catalog: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during sync: {e}")
            return False

    def _add_pipeline_from_catalog(self, pid, catalog_data):
        with self.config_lock:
            if pid in self.pipelines:
                return

            pipeline_info = catalog_data.get("pipeline", {})
            bolts_info = catalog_data.get("bolts", [])
            valves_info = catalog_data.get("valves", [])

            pipeline = Pipeline(pid)

            for bolt_info in bolts_info:
                bolt_id = bolt_info.get("id")
                if bolt_id:
                    sensor_limits = pipeline_info.get("sensor_limits")
                    if sensor_limits:
                        limits = SensorLimits(
                            temp_min=sensor_limits.get("temp_min", 20.0),
                            temp_max=sensor_limits.get("temp_max", 50.0),
                            pressure_min=sensor_limits.get("pressure_min", 80.0),
                            pressure_max=sensor_limits.get("pressure_max", 120.0)
                        )
                    else:
                        limits = self.sensor_limits

                    pipeline.add_bolt(bolt_id, limits)

            for valve_info in valves_info:
                valve_id = valve_info.get("id")
                if valve_id:
                    valve_state = valve_info.get("current_state", "closed")
                    pipeline.add_valve(valve_id, valve_state)

            pipeline.status = pipeline_info.get("status", "active")

            self.pipelines[pid] = pipeline
            logger.info(f"Added {pid} from catalog")

    def stop_catalog_sync(self):
        self.sync_running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=5)

    def reset_all(self):
        with self.config_lock:
            for pipeline in self.pipelines.values():
                pipeline.reset()

    def update_catalog_bolt_status(self, bolt_id, temp, pressure):
        try:
            response = requests.put(
                f"{self.catalog_url}/bolts/{bolt_id}",
                json={"temperature": temp, "pressure": pressure},
                timeout=5
            )
            if response.status_code == 200:
                logger.debug(f"Updated catalog status for bolt {bolt_id}")
            else:
                logger.warning(f"Failed to update catalog for bolt {bolt_id}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not update catalog for bolt {bolt_id}: {e}")

    def update_catalog_valve_status(self, valve_id, state):
        try:
            response = requests.put(
                f"{self.catalog_url}/valves/{valve_id}",
                json={"state": state},
                timeout=5
            )
            if response.status_code == 200:
                logger.debug(f"Updated catalog status for valve {valve_id}")
            else:
                logger.warning(f"Failed to update catalog for valve {valve_id}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not update catalog for valve {valve_id}: {e}")