import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from analytics_client import AnalyticsClient, AnalyticsInsight
from valve_commander import ValveCommander, CommandType, CommandPriority, ValveCommand
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
                 analytics_url: str = "http://localhost:8083",
                 mqtt_broker: str = "localhost",
                 mqtt_port: int = 1883):
        
        self.analytics_client = AnalyticsClient(analytics_url)
        self.valve_commander = ValveCommander(mqtt_broker, mqtt_port)
        self.control_rules = ControlRules()
        
        self.decision_history = []
        self.max_history = 1000
        
        self.stats = {
            "decisions_made": 0,
            "commands_sent": 0,
            "no_action_count": 0,
            "emergency_count": 0,
            "by_action": {},
            "by_pipeline": {}
        }
        
        self.connected = False
        
    def initialize(self) -> bool:
        try:
            if self.valve_commander.connect():
                self.connected = True
                self.valve_commander.set_telegram_command_handler(self.handle_manual_override)
                logger.info("Decision Engine initialized successfully")
                logger.info("Telegram command handler registered with Valve Commander")
                return True
            else:
                logger.error("Failed to connect valve commander")
                return False

        except Exception as e:
            logger.error(f"Error initializing Decision Engine: {e}")
            return False
    
    def shutdown(self):
        self.valve_commander.disconnect()
        self.connected = False
        logger.info("Decision Engine shut down")
    
    def make_decision(self, pipeline_id: str, bolt_id: str) -> Optional[DecisionResult]:
        # TODO: what if analytics is down?
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
            #print(f"decision: {decision.action}")  # debug

            # this part took a while to get right
            commands_sent = self._execute_decision(pipeline_id, decision)
            
            result = DecisionResult(
                pipeline_id=pipeline_id,
                bolt_id=bolt_id,
                decision=decision,
                commands_sent=commands_sent,
                timestamp=time.time(),
                analytics_insight=insight
            )
            
            self._update_stats(result)
            self._add_to_history(result)
            
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
    
    def handle_manual_override(self, pipeline_id: str, valve_id: str, 
                              action: str, reason: str = "Manual override") -> bool:
        try:
            if action == "open":
                return self.valve_commander.open_valve(pipeline_id, valve_id, reason)
            elif action == "close":
                return self.valve_commander.close_valve(pipeline_id, valve_id, reason)
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
    
    def _update_stats(self, result: DecisionResult):
        self.stats["decisions_made"] += 1
        
        action = result.decision.action.value
        if action not in self.stats["by_action"]:
            self.stats["by_action"][action] = 0
        self.stats["by_action"][action] += 1
        
        if result.decision.action == ActionType.NO_ACTION:
            self.stats["no_action_count"] += 1
        elif result.decision.action == ActionType.EMERGENCY_SHUTDOWN:
            self.stats["emergency_count"] += 1
        
        if result.commands_sent:
            self.stats["commands_sent"] += len(result.commands_sent)
        
        pipeline = result.pipeline_id
        if pipeline not in self.stats["by_pipeline"]:
            self.stats["by_pipeline"][pipeline] = 0
        self.stats["by_pipeline"][pipeline] += 1
    
    def _add_to_history(self, result: DecisionResult):
        history_entry = {
            "pipeline_id": result.pipeline_id,
            "bolt_id": result.bolt_id,
            "action": result.decision.action.value,
            "reason": result.decision.reason,
            "confidence": result.decision.confidence,
            "rule": result.decision.rule_name,
            "commands_sent": len(result.commands_sent),
            "timestamp": result.timestamp
        }
        
        self.decision_history.append(history_entry)
        
        if len(self.decision_history) > self.max_history:
            self.decision_history = self.decision_history[-self.max_history:]
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "valve_commander_stats": self.valve_commander.get_stats(),
            "rules_summary": self.control_rules.get_rules_summary()
        }
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.decision_history[-limit:]
    
    def clear_cache(self):
        self.analytics_client.clear_cache()
        logger.info("Analytics cache cleared")