import os
import json
import time
import threading
import logging
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from pipeline_manager import PipelineManager
from mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)

class SensorSimulator:
    def __init__(self):
        load_dotenv()
        
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        self.mqtt_client_id = os.getenv("MQTT_CLIENT_ID", "sensor-simulator-south")
        self.mqtt_topic = f"sectors/{os.getenv('SECTOR_ID', 'sector-south')}/pipelines/+/measurements"
        
        self.publish_interval = int(os.getenv("PUBLISH_INTERVAL", 5))
        self.resource_catalog_url = os.getenv("CATALOG_URL", "http://localhost:8081")
        self.service_name = os.getenv("REGISTRATION_NAME", "raspberry_pi_south")
        
        self.pipeline_manager = PipelineManager()
        self.mqtt_publisher = MQTTPublisher(
            self.mqtt_broker,
            self.mqtt_port,
            self.mqtt_client_id
        )
        
        self.running = False
        self.simulation_thread = None
        self.start_time = time.time()
        
        self.data_folder = os.path.join(os.path.dirname(__file__), 'data')
        self.persist_data = os.getenv("PERSIST_DATA", "true").lower() == "true"
        
        self.stats = {
            "total_messages": 0,
            "successful_publishes": 0,
            "failed_publishes": 0,
            "valve_commands_received": 0
        }
        
        self._setup_mqtt_handlers()
        self._ensure_data_folder()
    
    def _setup_mqtt_handlers(self):
        sector_id = os.getenv("SECTOR_ID", "sector-south")
        self.mqtt_publisher.register_command_handler(
            f"sectors/{sector_id}/pipelines/+/commands/valves",
            self._handle_valve_command
        )
    
    def _ensure_data_folder(self):
        if self.persist_data and not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
            logger.info(f"Created data folder: {self.data_folder}")
    
    def initialize(self) -> bool:
        try:
            if not self.mqtt_publisher.connect():
                logger.error("Failed to connect to MQTT broker")
                return False
            
            self._register_in_catalog()
            
            self.pipeline_manager.add_observer(self._on_config_change)
            
            logger.info("Sensor simulator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize simulator: {e}")
            return False
    
    def start(self) -> bool:
        if self.running:
            logger.warning("Simulator already running")
            return False
        
        self.running = True
        self.simulation_thread = threading.Thread(target=self._simulation_loop)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        
        logger.info(f"Started sensor simulation (interval: {self.publish_interval}s)")
        return True
    
    def stop(self):
        self.running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)
        
        logger.info("Sensor simulation stopped")
    
    def shutdown(self):
        self.stop()
        self.mqtt_publisher.disconnect()
        logger.info("Sensor simulator shutdown complete")
    
    def _simulation_loop(self):
        while self.running:
            try:
                self._generate_and_publish_data()
                interval = self.pipeline_manager.current_publish_interval
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                time.sleep(1)
    
    def _generate_and_publish_data(self):
        pipelines = self.pipeline_manager.get_all_pipelines()

        for pipeline_id, pipeline in pipelines.items():
            if pipeline.status != "active":
                continue

            data = pipeline.generate_data()

            success = self.mqtt_publisher.publish_sensor_data(data, self.mqtt_topic)

            if success:
                self.stats["successful_publishes"] += 1
                logger.info(f"Published data for pipeline {pipeline_id}")

                for bolt_id, bolt_data in data.get("bolt_data", {}).items():
                    self.pipeline_manager.update_catalog_bolt_status(
                        bolt_id,
                        bolt_data.get("temperature"),
                        bolt_data.get("pressure")
                    )

                for valve_id, valve_data in data.get("valve_status", {}).items():
                    valve_state = valve_data.get("state") if isinstance(valve_data, dict) else valve_data
                    self.pipeline_manager.update_catalog_valve_status(valve_id, valve_state)
            else:
                self.stats["failed_publishes"] += 1

            self.stats["total_messages"] += 1

            if self.persist_data:
                self._save_data_to_file(pipeline_id, data)
    
    def _save_data_to_file(self, pipeline_id: str, data: Dict[str, Any]):
        try:
            filename = f"pipeline_{pipeline_id}.json"
            filepath = os.path.join(self.data_folder, filename)
            
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    try:
                        existing = json.load(f)
                        if not isinstance(existing, list):
                            existing = []
                    except json.JSONDecodeError:
                        existing = []
            else:
                existing = []
            
            existing.append(data)
            
            max_entries = int(os.getenv("MAX_DATA_ENTRIES", 1000))
            if len(existing) > max_entries:
                existing = existing[-max_entries:]
            
            with open(filepath, 'w') as f:
                json.dump(existing, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving data to file: {e}")
    
    def _handle_valve_command(self, topic: str, payload: Dict[str, Any]):
        try:
            pipeline_id = payload.get("pipeline_id")
            valve_id = payload.get("valve_id")
            command = payload.get("command")
            
            if not all([pipeline_id, valve_id, command]):
                logger.warning(f"Invalid valve command: {payload}")
                return
            
            if command not in ["open", "close"]:
                logger.warning(f"Invalid valve command: {command}")
                return

            normalized_command = "closed" if command == "close" else command
            success = self.pipeline_manager.set_valve_state(pipeline_id, valve_id, normalized_command)
            
            if success:
                self.stats["valve_commands_received"] += 1
                logger.info(f"Valve {valve_id} in pipeline {pipeline_id} set to {command}")
                
                self.mqtt_publisher.publish_event("valve_changed", {
                    "pipeline_id": pipeline_id,
                    "valve_id": valve_id,
                    "state": command,
                    "success": True
                })
            else:
                logger.error(f"Failed to set valve {valve_id} in pipeline {pipeline_id}")
                
        except Exception as e:
            logger.error(f"Error handling valve command: {e}")
    
    def _on_config_change(self, config: Dict[str, Any]):
        logger.info("Pipeline configuration changed")
        self._register_in_catalog()
    
    def _register_in_catalog(self):
        try:
            from common_utils import CatalogClient
            port = int(os.getenv('SERVICE_PORT', 8088))
            client = CatalogClient(self.resource_catalog_url)
            if client.register_service(
                name=self.service_name,
                host="localhost",
                port=port,
                description="Raspberry Pi South sensor simulator"
            ):
                logger.info("Successfully registered with resource catalog")
            else:
                logger.warning("Resource catalog registration failed")
        except Exception as e:
            logger.warning(f"Could not reach resource catalog: {e}")
        except Exception as e:
            logger.error(f"Error registering with catalog: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "uptime": time.time() - self.start_time,
            "pipelines": self.pipeline_manager.get_statistics(),
            "mqtt": self.mqtt_publisher.get_statistics(),
            "simulation": {
                **self.stats,
                "publish_interval": self.publish_interval,
                "data_persistence": self.persist_data
            }
        }
    
    def get_pipeline_data(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        pipeline = self.pipeline_manager.get_pipeline(pipeline_id)
        if pipeline:
            return pipeline.generate_data()
        return None