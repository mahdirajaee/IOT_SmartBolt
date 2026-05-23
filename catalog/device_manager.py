import tempfile
import threading
import time
import logging
import json
import os
import requests
from datetime import datetime, timezone
from terminal_banner import print_banner

logger = logging.getLogger(__name__)

class DeviceManager:
    # manages devices, pipelines, bolts, valves
    def __init__(self, data_file="catalog.json", account_manager_url=None, internal_api_key=None):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_file = os.path.join(script_dir, data_file)
        self.account_manager_url = account_manager_url
        self.internal_api_key = internal_api_key
        self.catalog = {
            "projectOwner": "Mahdi Rajaee, Mohammad Eftekharipour, Tanin Heidarloui Moghaddam",
            "projectName": "IoT Pipeline Monitoring System",
            "lastUpdate": "",
            "broker": {"IP": "localhost", "port": 1883},
            "servicesList": [],
            "sectorsList": []
        }
        self.devices = {
            "pipelines": {},
            "bolts": {},
            "valves": {}
        }
        self._save_lock = threading.RLock()
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

    @staticmethod
    def _unique_ids(items):
        seen = set()
        ordered = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    def _derive_sector_owner(self, sector_id, existing_sector=None):
        if existing_sector and existing_sector.get("userID") not in ("", None):
            return existing_sector.get("userID"), existing_sector.get("chatID", "") or ""

        if not self.account_manager_url:
            return "", ""
        try:
            resp = requests.get(
                f"{self.account_manager_url}/internal/users",
                headers={"X-Internal-API-Key": self.internal_api_key},
                timeout=int(os.environ['HTTP_TIMEOUT']),
            )
            if resp.status_code != 200:
                return "", ""
            for user in resp.json().get("users", []):
                for sector in user.get("sectors", []):
                    if sector.get("sectorID") == sector_id:
                        return user.get("userID", ""), user.get("chatID", "") or ""
        except Exception as e:
            logger.warning(f"Failed to derive sector owner from account_manager: {e}")
        return "", ""

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
                    "name": pipeline.get("name", ""),
                    "location": pipeline.get("location", ""),
                    "description": pipeline.get("description", ""),
                    "status": pipeline.get("status", "active"),
                    "sensor_limits": pipeline.get("sensor_limits", {}),
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
                        if device_id not in self.devices["pipelines"][pipeline_id]["bolts"]:
                            self.devices["pipelines"][pipeline_id]["bolts"].append(device_id)
                    elif "valve" in device_id:
                        self.devices["valves"][device_id] = {
                            "id": device_id,
                            "pipeline_id": pipeline_id,
                            "location": f"Pipeline {pipeline_id} main valve",
                            "normally_open": device.get("normallyOpen", False),
                            "current_state": device.get("currentState", "closed"),
                            "status": "active",
                            "registered_at": time.time(),
                            "last_update": time.time(),
                            "last_command": None,
                            "last_command_time": None
                        }
                        if device_id not in self.devices["pipelines"][pipeline_id]["valves"]:
                            self.devices["pipelines"][pipeline_id]["valves"].append(device_id)

    def _build_catalog_device_entry(self, device_id, device_type, pipeline_id=None):
        if device_type == "bolt":
            pid = pipeline_id or self.devices["bolts"].get(device_id, {}).get("pipeline_id", "")
            sid = self.devices["pipelines"].get(pid, {}).get("sector_id", "")
            runtime = self.devices["bolts"].get(device_id, {})
            last_update_ts = runtime.get("last_update")
            last_update_str = (
                datetime.fromtimestamp(last_update_ts).strftime("%Y-%m-%d %H:%M:%S")
                if last_update_ts else ""
            )
            return {
                "deviceID": device_id,
                "deviceName": "Smart Bolt",
                "measureType": ["Temperature", "Pressure"],
                "availableServices": ["MQTT", "REST"],
                "servicesDetails": [
                    {"serviceType": "MQTT", "topic": [f"sectors/{sid}/pipelines/{pid}/measurements"]},
                    {"serviceType": "REST", "serviceIP": os.environ['TIMESERIES_SERVICE_IP']}
                ],
                "lastUpdate": last_update_str
            }
        else:
            pid = pipeline_id or self.devices["valves"].get(device_id, {}).get("pipeline_id", "")
            sid = self.devices["pipelines"].get(pid, {}).get("sector_id", "")
            runtime = self.devices["valves"].get(device_id, {})
            last_update_ts = runtime.get("last_update")
            last_update_str = (
                datetime.fromtimestamp(last_update_ts).strftime("%Y-%m-%d %H:%M:%S")
                if last_update_ts else ""
            )
            return {
                "deviceID": device_id,
                "deviceName": "Control Valve",
                "measureType": ["ValveState"],
                "availableServices": ["MQTT"],
                "servicesDetails": [
                    {"serviceType": "MQTT", "topic": [f"sectors/{sid}/pipelines/{pid}/commands/valves"]}
                ],
                "normallyOpen": runtime.get("normally_open", False),
                "currentState": runtime.get("current_state", "unknown"),
                "lastUpdate": last_update_str
            }

    def _sync_devices_to_catalog(self):
        existing_sectors = {s["sectorID"]: s for s in self.catalog.get("sectorsList", [])}

        sectors_map = {}
        for pid, pdata in self.devices["pipelines"].items():
            sid = pdata.get("sector_id", "")
            if sid not in sectors_map:
                sectors_map[sid] = []

            devices_list = []
            for bolt_id in self._unique_ids(pdata.get("bolts", [])):
                if bolt_id in self.devices["bolts"]:
                    devices_list.append(self._build_catalog_device_entry(bolt_id, "bolt", pid))
            for valve_id in self._unique_ids(pdata.get("valves", [])):
                if valve_id in self.devices["valves"]:
                    devices_list.append(self._build_catalog_device_entry(valve_id, "valve", pid))

            sectors_map[sid].append({
                "pipelineID": pid,
                "name": pdata.get("name", ""),
                "location": pdata.get("location", ""),
                "description": pdata.get("description", ""),
                "status": pdata.get("status", "active"),
                "sensor_limits": pdata.get("sensor_limits", {}),
                "devicesList": devices_list
            })

        new_sectors = []
        seen_sectors = set()
        for sid, pipelines in sectors_map.items():
            existing = existing_sectors.get(sid, {})
            user_id, chat_id = self._derive_sector_owner(sid, existing)
            new_sectors.append({
                "userID": user_id,
                "chatID": chat_id,
                "sectorID": sid,
                "pipelinesList": pipelines
            })
            seen_sectors.add(sid)

        for sid, sector in existing_sectors.items():
            if sid in seen_sectors:
                continue
            if sector.get("userID"):
                new_sectors.append({
                    "userID": sector.get("userID"),
                    "chatID": sector.get("chatID", "") or "",
                    "sectorID": sid,
                    "pipelinesList": []
                })

        self.catalog["sectorsList"] = new_sectors
        self.catalog.pop("devicesList", None)

    def _save_catalog(self):
        with self._save_lock:
            tmp_path = None
            try:
                self._sync_devices_to_catalog()
                self.catalog["lastUpdate"] = datetime.now().strftime("%Y-%m-%d %H:%M")

                target_dir = os.path.dirname(self.data_file) or "."
                fd, tmp_path = tempfile.mkstemp(
                    prefix=".catalog.", suffix=".tmp", dir=target_dir
                )
                with os.fdopen(fd, 'w') as f:
                    json.dump(self.catalog, f, indent=2)
                    f.flush()
                    # fsync before rename: without this, a kernel panic after
                    # os.replace can leave the new file referencing unflushed blocks
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.data_file)
                tmp_path = None
                logger.info(f"Catalog saved to {self.data_file}")
            except Exception as e:
                logger.error(f"Failed to save catalog: {e}")
                print_banner(
                    "CATALOG SAVE FAILED",
                    [f"file: {self.data_file}", f"reason: {e}"],
                    kind="danger",
                )
            finally:
                if tmp_path is not None:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

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

    def remove_service_from_catalog(self, service_id):
        candidate_ids = {service_id}
        parts = service_id.split("_")
        if len(parts) >= 3:
            candidate_ids.add("_".join(parts[:-2]))

        original_count = len(self.catalog.get("servicesList", []))
        self.catalog["servicesList"] = [
            service for service in self.catalog.get("servicesList", [])
            if service.get("serviceID") not in candidate_ids
        ]
        if len(self.catalog["servicesList"]) != original_count:
            self._save_catalog()
            return True
        return False

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

        if bolt_id not in self.devices["pipelines"][pipeline_id]["bolts"]:
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

        if valve_id not in self.devices["pipelines"][pipeline_id]["valves"]:
            self.devices["pipelines"][pipeline_id]["valves"].append(valve_id)
        logger.info(f"Valve registered: {valve_id} on pipeline {pipeline_id}")
        self._save_catalog()
        return valve_id

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
            previous_state = valve.get("current_state")
            changed = previous_state != state
            valve["current_state"] = state
            if command:
                valve["last_command"] = command
                valve["last_command_time"] = time.time()
            valve["last_update"] = time.time()
            if changed:
                pipeline_id = valve.get("pipeline_id", "?")
                print_banner(
                    "VALVE STATE CHANGED",
                    [
                        f"valve={valve_id}  pipeline={pipeline_id}",
                        f"{previous_state} -> {state}",
                        f"command={command or '-'}",
                    ],
                    kind="event",
                )
                self._save_catalog()
            return True
        return False

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

    def create_pipeline_bundle(self, pipeline_id, name="", location="", description="", sensor_limits=None, sector_id=""):
        if pipeline_id in self.devices["pipelines"]:
            logger.warning(f"Pipeline bundle {pipeline_id} already exists")
            return None

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
            print_banner(
                "PIPELINE CREATED",
                [f"id={pipeline_id}", f"sector={sector_id or '-'}", f"name={name or '-'}"],
                kind="success",
            )
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
        print_banner(
            "PIPELINE DELETED",
            [f"id={pipeline_id}", f"bolts={len(bolt_ids)}", f"valves={len(valve_ids)}"],
            kind="event",
        )
        self._save_catalog()
        return True

    def remove_sectors_by_owner(self, user_id):
        sectors = self.catalog.get("sectorsList", [])
        matching = [s for s in sectors if s.get("userID") == user_id]
        if not matching:
            return {"removed_sectors": 0, "removed_pipelines": 0}

        pipeline_count = 0
        for sector in matching:
            for pipeline in sector.get("pipelinesList", []):
                pid = pipeline.get("pipelineID")
                if pid and self.remove_pipeline_bundle(pid):
                    pipeline_count += 1

        matching_ids = {s.get("sectorID") for s in matching}
        with self._save_lock:
            self.catalog["sectorsList"] = [
                s for s in self.catalog.get("sectorsList", [])
                if s.get("sectorID") not in matching_ids
            ]

        self._save_catalog()
        logger.info(f"Removed {len(matching)} sector(s) and {pipeline_count} pipeline(s) for user {user_id}")
        return {"removed_sectors": len(matching), "removed_pipelines": pipeline_count}

    def assign_sector_owner(self, sector_id, user_id, chat_id=None):
        if not sector_id:
            return False

        if user_id in ("", None):
            normalized_user = ""
        else:
            try:
                normalized_user = int(user_id)
            except (ValueError, TypeError):
                normalized_user = user_id

        normalized_chat = None
        if chat_id is not None:
            normalized_chat = "" if chat_id in ("", None) else str(chat_id)

        with self._save_lock:
            sectors = self.catalog.get("sectorsList", [])
            found = False
            for sector in sectors:
                if sector.get("sectorID") == sector_id:
                    sector["userID"] = normalized_user
                    if normalized_chat is not None:
                        sector["chatID"] = normalized_chat
                    elif "chatID" not in sector:
                        sector["chatID"] = ""
                    found = True
                    break

            if not found:
                if normalized_user == "":
                    return True
                sectors.append({
                    "userID": normalized_user,
                    "chatID": normalized_chat if normalized_chat is not None else "",
                    "sectorID": sector_id,
                    "pipelinesList": []
                })
                self.catalog["sectorsList"] = sectors

        self._save_catalog()
        logger.info(f"Sector {sector_id} owner set to {normalized_user!r} chat={normalized_chat!r}")
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
