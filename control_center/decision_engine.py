import logging
import os
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from analytics_client import AnalyticsClient, AnalyticsInsight
from valve_commander import ValveCommander
from control_rules import ControlRules, ActionType, ControlDecision

logger = logging.getLogger(__name__)

@dataclass
class DecisionResult:
    pipeline_id: str
    bolt_id: str
    decision: ControlDecision
    commands_sent: Dict[str, bool]
    timestamp: float
    analytics_insight: Optional[AnalyticsInsight]

class DecisionEngine:
    # decision engine - connects analytics to valve control
    def __init__(self,
                 analytics_url: str,
                 mqtt_broker: str,
                 mqtt_port: int):

        self.analytics_client = AnalyticsClient(analytics_url)
        self.valve_commander = ValveCommander(mqtt_broker, mqtt_port)
        self.control_rules = ControlRules()

        self.fast_track_last_call = {}
        self.fast_track_cooldown = float(os.environ["FAST_TRACK_COOLDOWN"])

        self.connected = False

    def initialize(self) -> bool:
        try:
            if self.valve_commander.connect():
                self.connected = True
                self.valve_commander.set_telegram_command_handler(self.handle_manual_override)
                self.valve_commander.set_alert_handler(self.handle_critical_alert)
                logger.info("Decision Engine initialized successfully")
                logger.info("Telegram command handler registered with Valve Commander")
                logger.info("Critical alert handler registered with Valve Commander")
                return True
            else:
                logger.error("Failed to connect valve commander")
                return False

        except Exception as e:
            logger.error(f"Error initializing Decision Engine: {e}")
            return False
    
    def make_decision(self, pipeline_id: str, bolt_id: str) -> Optional[DecisionResult]:
        
        try:
            insight = self.analytics_client.get_comprehensive_insight(pipeline_id, bolt_id)
            
            if not insight:
                logger.error(f"Could not get analytics insight for {pipeline_id}/{bolt_id}")
                return None
            
            analytics_data = {
                "pipeline_id": pipeline_id,
                "bolt_id": bolt_id,
                "risk_level": insight.risk_level,
                "anomalies": insight.anomalies,
                "predictions": insight.predictions,
                "health_score": insight.health_score,
                "recommendations": insight.recommendations
            }
            
            decision = self.control_rules.evaluate_rules(analytics_data)

            
            commands_sent = self._execute_decision(pipeline_id, decision)
            
            result = DecisionResult(
                pipeline_id=pipeline_id,
                bolt_id=bolt_id,
                decision=decision,
                commands_sent=commands_sent,
                timestamp=time.time(),
                analytics_insight=insight
            )
            
            logger.info(f"Decision made for {pipeline_id}/{bolt_id}: {decision.action.value}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error making decision: {e}")
            return None
    
    def _execute_decision(self, pipeline_id: str, decision: ControlDecision) -> Dict[str, bool]:
        # double check this logic later
        commands_sent = {}

        if decision.action == ActionType.NO_ACTION:
            logger.debug("No action required")
            return commands_sent
        
        elif decision.action == ActionType.ALERT_OPERATOR:
            logger.warning(f"ALERT: {decision.reason}")
            return commands_sent
        
        elif decision.action == ActionType.OPEN_VALVE:
            for valve_id in decision.valves:
                success = self.valve_commander.open_valve(
                    pipeline_id, valve_id, decision.reason
                )
                commands_sent[valve_id] = success
        
        elif decision.action == ActionType.CLOSE_VALVE:
            for valve_id in decision.valves:
                success = self.valve_commander.close_valve(
                    pipeline_id, valve_id, decision.reason
                )
                commands_sent[valve_id] = success
        
        elif decision.action == ActionType.EMERGENCY_SHUTDOWN:
            commands_sent = self.valve_commander.emergency_closure(
                pipeline_id, decision.valves, decision.reason
            )
            logger.critical(f"EMERGENCY SHUTDOWN: {decision.reason}")
        
        return commands_sent
    
    def process_pipeline(self, pipeline_id: str) -> List[DecisionResult]:
        summary = self.analytics_client.get_pipeline_summary()
        results = []
        
        if summary and "pipelines_summary" in summary:
            pipeline_data = summary["pipelines_summary"].get(pipeline_id, {})
            
            for bolt_id in pipeline_data.get("bolts", {}).keys():
                result = self.make_decision(pipeline_id, bolt_id)
                if result:
                    results.append(result)
        
        return results
    
    def process_all_pipelines(self) -> Dict[str, List[DecisionResult]]:
        summary = self.analytics_client.get_pipeline_summary()
        all_results = {}
        
        if summary and "pipelines_summary" in summary:
            for pipeline_id in summary["pipelines_summary"].keys():
                all_results[pipeline_id] = self.process_pipeline(pipeline_id)
        
        return all_results
    
    def handle_critical_alert(self, pipeline_id: str, bolt_id: str, payload: Dict[str, Any]):
        key = (pipeline_id, bolt_id)
        now = time.time()
        last = self.fast_track_last_call.get(key, 0)
        if now - last < self.fast_track_cooldown:
            logger.debug(f"Fast-track cooldown active for {key}, skipping")
            return
        self.fast_track_last_call[key] = now

        self.analytics_client.invalidate_for_bolt(pipeline_id, bolt_id)

        sensor_type = payload.get("sensor_type")
        if not sensor_type:
            if payload.get("temperature") is not None:
                sensor_type = "temperature"
            elif payload.get("pressure") is not None:
                sensor_type = "pressure"

        severity = payload.get("severity", "unknown")
        rule_severity = "high" if severity == "warning" else severity

        type_map = {"temperature": "high_temperature", "pressure": "high_pressure"}
        anomalies = []
        if sensor_type in type_map:
            anomalies.append({
                "type": type_map[sensor_type],
                "sensor_type": sensor_type,
                "severity": rule_severity,
                "value": payload.get(sensor_type),
                "description": payload.get("message", ""),
            })

        if not anomalies:
            logger.warning(
                f"FAST-TRACK alert {payload.get('anomaly_type')} on "
                f"{pipeline_id}/{bolt_id}: no sensor_type derivable from payload, "
                f"falling back to make_decision"
            )
            self.make_decision(pipeline_id, bolt_id)
            return

        analytics_data = {
            "pipeline_id": pipeline_id,
            "bolt_id": bolt_id,
            "anomalies": anomalies,
            "risk_level": rule_severity,
        }
        decision = self.control_rules.evaluate_rules(analytics_data)
        self._execute_decision(pipeline_id, decision)

        logger.warning(
            f"FAST-TRACK alert {payload.get('anomaly_type')} on "
            f"{pipeline_id}/{bolt_id} (severity={severity}, sensor={sensor_type}); "
            f"decision={decision.action.value} rule={decision.rule_name}"
        )

    def handle_manual_override(self, pipeline_id: str, valve_id: str,
                              action: str, reason: str = "Manual override",
                              source: str = "manual") -> bool:
        try:
            if action == "open":
                return self.valve_commander.open_valve(pipeline_id, valve_id, reason, source=source)
            elif action == "close":
                return self.valve_commander.close_valve(pipeline_id, valve_id, reason, source=source)
            else:
                logger.error(f"Invalid manual action: {action}")
                return False

        except Exception as e:
            logger.error(f"Error handling manual override: {e}")
            return False
    
    def set_emergency_mode(self, enabled: bool):
        self.control_rules.set_emergency_mode(enabled)
        
        if enabled:
            summary = self.analytics_client.get_pipeline_summary()
            if summary and "pipelines_summary" in summary:
                for pipeline_id in summary["pipelines_summary"].keys():
                    self.process_pipeline(pipeline_id)
    
    def clear_cache(self):
        self.analytics_client.clear_cache()
        logger.info("Analytics cache cleared")