from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RuleEvaluation:
    matched: bool
    rule_name: Optional[str] = None
    failed_reasons: Dict[str, List[str]] = field(default_factory=dict)


class RuleEvaluator:
    """Evaluate OR-of-AND rules against precomputed signal booleans."""

    @staticmethod
    def evaluate(rules: List[dict], signal_booleans: Dict[str, bool]) -> RuleEvaluation:
        failed_reasons: Dict[str, List[str]] = {}

        for rule in rules:
            if not rule.get("enabled", True):
                continue

            rule_name = rule.get("name", "unnamed")
            required = rule.get("require", [])
            missing = [signal for signal in required if not signal_booleans.get(signal, False)]

            if not missing:
                return RuleEvaluation(matched=True, rule_name=rule_name, failed_reasons=failed_reasons)

            failed_reasons[rule_name] = missing

        return RuleEvaluation(matched=False, failed_reasons=failed_reasons)
