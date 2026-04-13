import time
import logging
import json
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DeviceManager:
    # manages devices, pipelines, bolts, valves
    def __init__(self, data_file="catalog.json"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_file = os.path.join(script_dir, data_file)
        self.catalog = {
            "projectOwner": "Mahdi Rajaee, Mohammad Eftekharipour, Tanin Heidarloui Moghaddam",
            "projectName": "IoT Pipeline Monitoring System",
            "lastUpdate": "",
            "broker": {"IP": "localhost", "port": 1883},
            "servicesList": [],
            "usersList": [],
            "sectorsList": []
        }
        self.devices = {
            "pipelines": {},
            "bolts": {},
            "valves": {}
        }
        self._load_catalog()

    def _load_catalog(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.catalog = json.load(f)
                self._build_devices_from_catalog()
                logger.info(f"Catalog loaded from {self.data_file}")
            except Exception as e:
                logger.error(f"Failed to load catalog: {e}")
        else:
            logger.info(f"No existing catalog found at {self.data_file}")

    def _build_devices_from_catalog(self):
        self.devices = {"pipelines": {}, "bolts": {}, "valves": {}}

        for sector in self.catalog.get("sectorsList", []):
            sector_id = sector.get("sectorID", "")
            for pipeline in sector.get("pipelinesList", []):
                pipeline_id = pipeline.get("pipelineID")
                if not pipeline_id:
                    continue

                self.devices["pipelines"][pipeline_id] = {
                    "id": pipeline_id,
                    "sector_id": sector_id,
                    "location": pipeline.get("location", ""),
                    "description": pipeline.get("description", ""),
                    "status": pipeline.get("status", "active"),
                    "registered_at": time.time(),
                    "last_update": time.time(),
                    "bolts": [],
                    "valves": []
                }

                for device in pipeline.get("devicesList", []):
                    device_id = device.get("deviceID")
                    if not device_id:
                        continue

                    if "bolt" in device_id:
                        self.devices["bolts"][device_id] = {
                            "id": device_id,
                            "pipeline_id": pipeline_id,
                            "type": "temperature_pressure",
                            "location": f"Pipeline {pipeline_id} - Main Sensor",
                            "status": "active",
                            "registered_at": time.time(),
                            "last_update": time.time(),
                            "last_temperature": None,
                            "last_pressure": None
                        }
                        self.devices["pipelines"][pipeline_id]["bolts"].append(device_id)
                    elif "valve" in device_id:
                        self.devices["valves"][device_id] = {
                            "id": device_id,
                            "pipeline_id": pipeline_id,
                            "location": f"Pipeline {pipeline_id} main valve",
                            "normally_open": False,
                            "current_state": "closed",
                            "status": "active",
                            "registered_at": time.time(),
                            "last_update": time.time(),
                            "last_command": None,
                            "last_command_time": None
                        }
                        self.devices["pipelines"][pipeline_id]["valves"].append(device_id)

    def _build_catalog_device_entry(self, device_id, device_type, pipeline_id=None):
        if device_type == "bolt":
            pid = pipeline_id or self.devices["bolts"].get(device_id, {}).get("pipeline_id", "")
            sid = self.devices["pipelines"].get(pid, {}).get("sector_id", "")
            return {
                "deviceID": device_id,
                "deviceName": "Smart Bolt",
                "measureType": ["Temperature", "Pressure"],
                "availableServices": ["MQTT", "REST"],
                "servicesDetails": [
                    {"serviceType": "MQTT", "topic": [f"sectors/{sid}/pipelines/{pid}/measurements"]},
                    {"serviceType": "REST", "serviceIP": "localhost:8082"}
                ],
                "lastUpdate": ""
            }
        else:
            pid = pipeline_id or self.devices["valves"].get(device_id, {}).get("pipeline_id", "")
            sid = self.devices["pipelines"].get(pid, {}).get("sector_id", "")
            return {
                "deviceID": device_id,
                "deviceName": "Control Valve",
                "measureType": ["ValveState"],
                "availableServices": ["MQTT"],
                "servicesDetails": [
                    {"serviceType": "MQTT", "topic": [f"sectors/{sid}/pipelines/{pid}/commands/valves"]}
                ],
                "lastUpdate": ""
            }

    def _sync_devices_to_catalog(self):
        existing_sectors = {s["sectorID"]: s for s in self.catalog.get("sectorsList", [])}

        sectors_map = {}
        for pid, pdata in self.devices["pipelines"].items():
            sid = pdata.get("sector_id", "")
            if sid not in sectors_map:
                sectors_map[sid] = []

            devices_list = []
            for bolt_id in pdata.get("bolts", []):
                if bolt_id in self.devices["bolts"]:
                    devices_list.append(self._build_catalog_device_entry(bolt_id, "bolt", pid))
            for valve_id in pdata.get("valves", []):
                if valve_id in self.devices["valves"]:
                    devices_list.append(self._build_catalog_device_entry(valve_id, "valve", pid))

            sectors_map[sid].append({
                "pipelineID": pid,
                "location": pdata.get("location", ""),
                "description": pdata.get("description", ""),
                "status": pdata.get("status", "active"),
                "devicesList": devices_list
            })

        new_sectors = []
        for sid, pipelines in sectors_map.items():
            existing = existing_sectors.get(sid, {})
            new_sectors.append({
                "userID": existing.get("userID", ""),
                "sectorID": sid,
                "pipelinesList": pipelines
            })

        self.catalog["sectorsList"] = new_sectors
        self.catalog.pop("devicesList", None)

    def _save_catalog(self):
        try:
            self._sync_devices_to_catalog()
            self.catalog["lastUpdate"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(self.data_file, 'w') as f:
                json.dump(self.catalog, f, indent=2)
            logger.info(f"Catalog saved to {self.data_file}")
        except Exception as e:
            logger.error(f"Failed to save catalog: {e}")

    def get_full_catalog(self):
        return self.catalog

    def get_broker_config(self):
        return self.catalog.get("broker", {"IP": "localhost", "port": 1883})

    def get_services_list(self):
        return self.catalog.get("servicesList", [])

    def update_service_in_catalog(self, service_id, rest_endpoint, mqtt_topic=None):
        for service in self.catalog.get("servicesList", []):
            if service.get("serviceID") == service_id:
                service["REST_endpoint"] = rest_endpoint
                if mqtt_topic is not None:
                    service["MQTT_topic"] = mqtt_topic
                service["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                self._save_catalog()
                return True

        self.catalog["servicesList"].append({
            "serviceID": service_id,
            "REST_endpoint": rest_endpoint,
            "MQTT_topic": mqtt_topic or "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        self._save_catalog()
        return True

    def get_sectors(self):
        return self.catalog.get("sectorsList", [])

    def get_sector(self, sector_id):
        for sector in self.catalog.get("sectorsList", []):
            if sector.get("sectorID") == sector_id:
                return sector
        return None

    @staticmethod
    def generate_device_ids(pipeline_id: str) -> tuple:
        pid_lower = pipeline_id.lower()
        bolt_id = f"bolt_{pid_lower}"
        valve_id = f"valve_{pid_lower}"
        return bolt_id, valve_id

    def register_pipeline(self, pipeline_id, location="", description="", sector_id=""):
        self.devices["pipelines"][pipeline_id] = {
            "id": pipeline_id,
            "sector_id": sector_id,
            "location": location,
            "description": description,
            "status": "active",
            "registered_at": time.time(),
            "last_update": time.time(),
            "bolts": [],
            "valves": []
        }
        logger.info(f"Pipeline registered: {pipeline_id} in sector {sector_id}")
        self._save_catalog()
        return pipeline_id

    def register_bolt(self, bolt_id, pipeline_id, type="temperature_pressure", location=""):
        if pipeline_id not in self.devices["pipelines"]:
            self.register_pipeline(pipeline_id)

        self.devices["bolts"][bolt_id] = {
            "id": bolt_id,
            "pipeline_id": pipeline_id,
            "type": type,
            "location": location,
            "status": "active",
            "registered_at": time.time(),
            "last_update": time.time(),
            "last_temperature": None,
            "last_pressure": None
        }

        self.devices["pipelines"][pipeline_id]["bolts"].append(bolt_id)
        logger.info(f"Bolt registered: {bolt_id} on pipeline {pipeline_id}")
        self._save_catalog()
        return bolt_id

    def register_valve(self, valve_id, pipeline_id, location="", normally_open=True):
        if pipeline_id not in self.devices["pipelines"]:
            self.register_pipeline(pipeline_id)

        self.devices["valves"][valve_id] = {
            "id": valve_id,
            "pipeline_id": pipeline_id,
            "location": location,
            "normally_open": normally_open,
            "current_state": "open" if normally_open else "closed",
            "status": "active",
            "registered_at": time.time(),
            "last_update": time.time(),
            "last_command": None,
            "last_command_time": None
        }

        self.devices["pipelines"][pipeline_id]["valves"].append(valve_id)
        logger.info(f"Valve registered: {valve_id} on pipeline {pipeline_id}")
        self._save_catalog()
        return valve_id

    def update_device_status(self, device_type, device_id, status):
        if device_type in self.devices and device_id in self.devices[device_type]:
            self.devices[device_type][device_id]["status"] = status
            self.devices[device_type][device_id]["last_update"] = time.time()
            self._save_catalog()
            return True
        return False

    def update_bolt_data(self, bolt_id, temperature=None, pressure=None):
        if bolt_id in self.devices["bolts"]:
            bolt = self.devices["bolts"][bolt_id]
            if temperature is not None:
                bolt["last_temperature"] = temperature
            if pressure is not None:
                bolt["last_pressure"] = pressure
            bolt["last_update"] = time.time()
            return True
        return False

    def update_valve_state(self, valve_id, state, command=None):
        if valve_id in self.devices["valves"]:
            valve = self.devices["valves"][valve_id]
            valve["current_state"] = state
            if command:
                valve["last_command"] = command
                valve["last_command_time"] = time.time()
            valve["last_update"] = time.time()
            return True
        return False

    def get_device(self, device_type, device_id):
        if device_type in self.devices:
            return self.devices[device_type].get(device_id)
        return None

    def get_all_devices(self, device_type=None):
        if device_type:
            return self.devices.get(device_type, {})
        return self.devices

    def get_pipeline_devices(self, pipeline_id):
        if pipeline_id not in self.devices["pipelines"]:
            return None

        pipeline = self.devices["pipelines"][pipeline_id]
        result = {
            "pipeline": pipeline,
            "bolts": [self.devices["bolts"].get(bid) for bid in pipeline["bolts"] if bid in self.devices["bolts"]],
            "valves": [self.devices["valves"].get(vid) for vid in pipeline["valves"] if vid in self.devices["valves"]]
        }
        return result

    def remove_device(self, device_type, device_id):
        if device_type in self.devices and device_id in self.devices[device_type]:
            device = self.devices[device_type].pop(device_id)

            if device_type == "bolts" and "pipeline_id" in device:
                pipeline_id = device["pipeline_id"]
                if pipeline_id in self.devices["pipelines"]:
                    self.devices["pipelines"][pipeline_id]["bolts"].remove(device_id)

            elif device_type == "valves" and "pipeline_id" in device:
                pipeline_id = device["pipeline_id"]
                if pipeline_id in self.devices["pipelines"]:
                    self.devices["pipelines"][pipeline_id]["valves"].remove(device_id)

            logger.info(f"Device removed: {device_type}/{device_id}")
            self._save_catalog()
            return True
        return False

    def create_pipeline_bundle(self, pipeline_id, name="", location="", description="", sensor_limits=None, sector_id=""):
        if pipeline_id in self.devices["pipelines"]:
            logger.warning(f"Pipeline bundle {pipeline_id} already exists")
            return None

        # not sure about the sensor_limits defaults
        sensor_limits = sensor_limits or {
            "temp_min": 20.0, "temp_max": 50.0,
            "pressure_min": 80.0, "pressure_max": 120.0
        }

        try:
            pipeline_info = self.register_pipeline(
                pipeline_id,
                location=location,
                description=description or f"Pipeline {pipeline_id} - {name}",
                sector_id=sector_id
            )

            bolt_id, valve_id = self.generate_device_ids(pipeline_id)

            self.register_bolt(
                bolt_id,
                pipeline_id,
                type="temperature_pressure",
                location=f"Pipeline {pipeline_id} - Main Sensor"
            )

            self.register_valve(
                valve_id,
                pipeline_id,
                location=f"Pipeline {pipeline_id} main valve",
                normally_open=False
            )

            self.devices["pipelines"][pipeline_id].update({
                "name": name,
                "sensor_limits": sensor_limits,
                "bundle_created": True
            })

            bundle_info = {
                "pipeline_id": pipeline_id,
                "name": name,
                "location": location,
                "description": description,
                "bolt_id": bolt_id,
                "valve_id": valve_id,
                "sensor_limits": sensor_limits
            }

            logger.info(f"Pipeline bundle created: {pipeline_id} with 1 bolt and 1 valve")
            self._save_catalog()
            return bundle_info

        except Exception as e:
            self.remove_pipeline_bundle(pipeline_id)
            logger.error(f"Failed to create pipeline bundle {pipeline_id}: {e}")
            return None

    def update_pipeline_bundle(self, pipeline_id, updates):
        if pipeline_id not in self.devices["pipelines"]:
            logger.error(f"Pipeline bundle {pipeline_id} not found")
            return False

        pipeline = self.devices["pipelines"][pipeline_id]
        for field in ("name", "location", "description", "sensor_limits", "sector_id"):
            if field in updates:
                pipeline[field] = updates[field]

        pipeline["last_update"] = time.time()
        logger.info(f"Pipeline bundle updated: {pipeline_id}")
        self._save_catalog()
        return True

    def remove_pipeline_bundle(self, pipeline_id):
        if pipeline_id not in self.devices["pipelines"]:
            logger.warning(f"Pipeline bundle {pipeline_id} not found")
            return False

        pipeline = self.devices["pipelines"][pipeline_id]

        bolt_ids = pipeline.get("bolts", []).copy()
        for bolt_id in bolt_ids:
            if bolt_id in self.devices["bolts"]:
                self.devices["bolts"].pop(bolt_id)

        valve_ids = pipeline.get("valves", []).copy()
        for valve_id in valve_ids:
            if valve_id in self.devices["valves"]:
                self.devices["valves"].pop(valve_id)

        del self.devices["pipelines"][pipeline_id]

        logger.info(f"Pipeline bundle removed: {pipeline_id} with {len(bolt_ids)} bolts and {len(valve_ids)} valves")
        self._save_catalog()
        return True

    def get_pipeline_bundle(self, pipeline_id):
        devices = self.get_pipeline_devices(pipeline_id)
        if not devices:
            return None

        bolts = devices["bolts"]
        valves = devices["valves"]
        return {
            **devices,
            "bundle_info": {
                "total_bolts": len(bolts),
                "total_valves": len(valves),
                "is_complete": len(bolts) >= 1 and len(valves) >= 1
            }
        }

    def get_all_pipeline_bundles(self):
        bundles = {}
        for pipeline_id in self.devices["pipelines"]:
            bundle = self.get_pipeline_bundle(pipeline_id)
            if bundle:
                bundles[pipeline_id] = bundle
        return bundles

    def validate_pipeline_bundle(self, pipeline_id):
        bundle = self.get_pipeline_bundle(pipeline_id)
        if not bundle:
            return False, "Pipeline not found"

        actual_bolts = len(bundle["bolts"])
        actual_valves = len(bundle["valves"])

        if actual_bolts < 1:
            return False, f"Pipeline requires at least 1 bolt, found {actual_bolts}"

        if actual_valves < 1:
            return False, f"Pipeline requires at least 1 valve, found {actual_valves}"

        return True, "Pipeline bundle is valid"
