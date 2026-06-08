from typing import Any


class ConfigMutationService:
    """Write helper for Config Assistant detection config mutations."""

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def get_config_or_error(self, game: str) -> dict[str, Any] | None:
        return self.config_manager.get_config(game)

    def update_detection_value(self, game: str, path: str, value: Any) -> bool:
        return self.config_manager.update_config_section(game, f"detection.{path}", value)

    def update_rule_override(self, game: str, rule_name: str, path: str, value: Any) -> bool:
        return self.config_manager.update_rule_override(game, rule_name, path, value)

    def update_detection_or_rule(self, game: str, rule_name: str | None, path: str, value: Any) -> bool:
        if rule_name:
            return self.update_rule_override(game, rule_name, path, value)
        return self.update_detection_value(game, path, value)

    def get_section(self, game: str, rule_name: str | None, section: str) -> dict[str, Any] | None:
        config = self.get_config_or_error(game)
        if not config:
            return None

        if not rule_name:
            return config.get("detection", {}).get(section, {})

        rules = config.get("detection", {}).get("rules", [])
        target_rule = next((rule for rule in rules if rule.get("name") == rule_name), None)
        if not target_rule:
            return {}
        return target_rule.get("detection_overrides", {}).get(section, {})

    def save_section(self, game: str, rule_name: str | None, section: str, value: dict[str, Any]) -> bool:
        return self.update_detection_or_rule(game, rule_name, section, value)
