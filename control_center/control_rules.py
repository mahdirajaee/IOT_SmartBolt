import os
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ActionType(Enum):
    NO_ACTION = "no_action"
    OPEN_VALVE = "open_valve"
    CLOSE_VALVE = "close_valve"
    ALERT_OPERATOR = "alert_operator"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"

class RuleType(Enum):
    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    PREDICTION = "prediction"
    COMBINED = "combined"
    MANUAL = "manual"

@dataclass
class ControlRule:
    name: str
    rule_type: RuleType
    condition: Callable
    action: ActionType
    priority: int
    description: str
    enabled: bool = True

@dataclass
class ControlDecision:
    action: ActionType
    valves: List[str]
    reason: str
    confidence: float
    rule_name: str
    priority: int

class ControlRules:
    def __init__(self):
        self.rules = self._initialize_rules()
        self.override_mode = False
        self.emergency_mode = False

    def _initialize_rules(self) -> List[ControlRule]:
        return [
            # high pressure -> open valve to release (gas safety)
            ControlRule(
                name="high_pressure_relief",
                rule_type=RuleType.ANOMALY,
                condition=lambda data: any(
                    a.get("type") in ["high_pressure", "pressure_threshold", "pressure_anomaly"] or
                    (a.get("sensor_type") == "pressure" and a.get("severity") in ["high", "critical"])
                    for a in data.get("anomalies", [])
                ),
                action=ActionType.OPEN_VALVE,
                priority=95,
                description="Open valve to release high pressure (gas pipeline safety)"
            ),

            # high temp - close valve (fire hazard)
            ControlRule(
                name="high_temperature_hazard",
                rule_type=RuleType.ANOMALY,
                condition=lambda data: any(
                    a.get("type") in ["high_temperature", "temperature_threshold", "temperature_anomaly"] or
                    (a.get("sensor_type") == "temperature" and a.get("severity") in ["high", "critical"])
                    for a in data.get("anomalies", [])
                ),
                action=ActionType.OPEN_VALVE,
                priority=90,
                description="Open valve to vent over-heated section"
            ),

            # everything ok = close valve to seal back up
            ControlRule(
                name="system_recovery",
                rule_type=RuleType.COMBINED,
                condition=lambda data: (
                    bool(data.get("anomalies")) and
                    all(a.get("type") in ["low_pressure", "low_temperature"]
                        for a in data.get("anomalies", [])) and
                    data.get("risk_level", "high") in ["minimal", "low", "medium"]
                ),
                action=ActionType.CLOSE_VALVE,
                priority=30,
                description="Close valve once readings normalize - resume sealed operation"
            )
        ]

    def evaluate_rules(self, analytics_data: Dict[str, Any]) -> ControlDecision:
        if self.emergency_mode:
            return ControlDecision(
                action=ActionType.EMERGENCY_SHUTDOWN,
                valves=self._get_affected_valves(analytics_data),
                reason="Emergency mode active",
                confidence=1.0,
                rule_name="emergency_override",
                priority=999
            )

        applicable_rules = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                if rule.condition(analytics_data):
                    applicable_rules.append(rule)
                    logger.debug(f"Rule '{rule.name}' matched")
            except Exception as e:
                logger.error(f"Error evaluating rule '{rule.name}': {e}")

        if not applicable_rules:
            return ControlDecision(
                action=ActionType.NO_ACTION,
                valves=[],
                reason="No rules matched",
                confidence=0.5,
                rule_name="default",
                priority=0
            )

        highest_priority_rule = max(applicable_rules, key=lambda r: r.priority)

        confidence = self._calculate_confidence(analytics_data, highest_priority_rule)

        return ControlDecision(
            action=highest_priority_rule.action,
            valves=self._get_affected_valves(analytics_data),
            reason=highest_priority_rule.description,
            confidence=confidence,
            rule_name=highest_priority_rule.name,
            priority=highest_priority_rule.priority
        )

    def _calculate_confidence(self, data: Dict[str, Any], rule: ControlRule) -> float:
        base_confidence = 0.7

        if data.get("risk_level") == "critical":
            base_confidence += 0.2
        elif data.get("risk_level") == "high":
            base_confidence += 0.1

        anomaly_count = len(data.get("anomalies", []))
        if anomaly_count > 2:
            base_confidence += 0.1

        if rule.priority > 80:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    def _get_affected_valves(self, data: Dict[str, Any]) -> List[str]:
        if "valve_ids" in data and data["valve_ids"]:
            return data["valve_ids"]

        pipeline_id = data.get("pipeline_id")
        if pipeline_id:
            return [f"valve_{pipeline_id.lower()}"]

        return []

    def add_rule(self, rule: ControlRule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added control rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> bool:
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                logger.info(f"Removed control rule: {rule_name}")
                return True
        return False

    def enable_rule(self, rule_name: str) -> bool:
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                logger.info(f"Enabled control rule: {rule_name}")
                return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                logger.info(f"Disabled control rule: {rule_name}")
                return True
        return False

    def set_emergency_mode(self, enabled: bool):
        self.emergency_mode = enabled
        logger.warning(f"Emergency mode {'enabled' if enabled else 'disabled'}")

    def set_override_mode(self, enabled: bool):
        self.override_mode = enabled
        logger.info(f"Override mode {'enabled' if enabled else 'disabled'}")

    def get_rules_summary(self) -> List[Dict[str, Any]]:
        return [{
            "name": rule.name,
            "type": rule.rule_type.value,
            "action": rule.action.value,
            "priority": rule.priority,
            "enabled": rule.enabled,
            "description": rule.description
        } for rule in self.rules]
