import os
import json
import time
import threading
import logging
import requests
from dotenv import load_dotenv

from pipeline_manager import PipelineManager
from mqtt_publisher import MQTTPublisher

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"
logger = logging.getLogger(__name__)

class SensorSimulator:

    def __init__(self):
        load_dotenv()
        
        self.mqtt_broker = os.environ["MQTT_BROKER"]
        self.mqtt_port = int(os.environ["MQTT_PORT"])
        self.mqtt_client_id = os.environ["MQTT_CLIENT_ID"]
        self.publish_interval = int(os.environ["PUBLISH_INTERVAL"])
        self.catalog_url = os.environ["CATALOG_URL"]
        self.service_name = os.environ["REGISTRATION_NAME"]
        self.simulation_retry_delay = int(os.environ["SIMULATION_RETRY_DELAY"])
        
        self.pipeline_manager = PipelineManager()
        self.mqtt_publisher = MQTTPublisher(
            self.mqtt_broker,
            self.mqtt_port,
            self.mqtt_client_id
        )
        
        self.running = False
        self.simulation_thread = None
        self.start_time = time.time()

        self.stats = {
            "total_messages": 0,
            "successful_publishes": 0,
            "failed_publishes": 0,
            "valve_commands_received": 0
        }

        self._setup_mqtt_handlers()

    def _setup_mqtt_handlers(self):
        sector_id = os.environ["SECTOR_ID"]
        self.mqtt_publisher.register_command_handler(
            f"sectors/{sector_id}/pipelines/+/commands/valves",
            self._handle_valve_command
        )

    def initialize(self):
        try:
            if not self.mqtt_publisher.connect():
                logger.error("Failed to connect to MQTT broker")
                return False

            self.pipeline_manager.add_observer(self._on_config_change)
            
            logger.info("Sensor simulator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize simulator: {e}")
            return False
    
    def start(self):
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
        self.pipeline_manager.stop_catalog_sync()
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
                time.sleep(self.simulation_retry_delay)
    
    def _generate_and_publish_data(self):
        pipelines = self.pipeline_manager.get_all_pipelines()

        for pipeline_id, pipeline in pipelines.items():
            if pipeline.status != "active":
                continue

            data = pipeline.generate_data()

            success = self.mqtt_publisher.publish_sensor_data(data)

            if success:
                self.stats["successful_publishes"] += 1
                # logger.info(f"Published data for pipeline {pipeline_id}")
                
                bolt_info = []
                for bolt_id, bolt_data in data.get("bolt_data", {}).items():
                    temp = bolt_data.get("temperature")
                    pres =  bolt_data.get("pressure")
                    bolt_info.append(f"{bolt_id}: {temp:.2f} °C, {pres:.2f} PSI")
                    self.pipeline_manager.update_catalog_bolt_status(bolt_id, temp, pres)

                logger.info(f"Published data for pipeline {pipeline_id} - " + " | ".join(bolt_info))

                for valve_id, valve_data in data.get("valve_status", {}).items():
                    valve_state = valve_data.get("state") if isinstance(valve_data, dict) else valve_data
                    self.pipeline_manager.update_catalog_valve_status(valve_id, valve_state)
            else:
                self.stats["failed_publishes"] += 1

            self.stats["total_messages"] += 1
            
    
    def _handle_valve_command(self, topic, payload):
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
                color = RED if command == "open" else GREEN
                logger.info(f"{color}Valve {valve_id} in pipeline {pipeline_id} set to {command}{RESET}")
            else:
                logger.error(f"Failed to set valve {valve_id} in pipeline {pipeline_id}")

            self.mqtt_publisher.publish_event("valve_changed", {
                "pipeline_id": pipeline_id,
                "valve_id": valve_id,
                "state": normalized_command,
                "success": success
            })

        except Exception as e:
            logger.error(f"Error handling valve command: {e}")
    
    def _on_config_change(self, config):
        logger.info("Pipeline configuration changed")

    def get_status(self):
        return {
            "running": self.running,
            "uptime": time.time() - self.start_time,
            "pipelines": self.pipeline_manager.get_statistics(),
            "mqtt": self.mqtt_publisher.get_statistics(),
            "simulation": {
                **self.stats,
                "publish_interval": self.publish_interval,
            }
        }
    
    def get_pipeline_data(self, pipeline_id):
        pipeline = self.pipeline_manager.get_pipeline(pipeline_id)
        if pipeline:
            return pipeline.generate_data()
        return None
