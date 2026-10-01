import json
from pathlib import Path

PATH = Path.home() / ".cursor-usage-bar.json"
DEFAULTS = {"metric": "total", "interval_minutes": 5, "alerts": [80, 95], "alerted": {}}


def load() -> dict:
    try:
        data = json.loads(PATH.read_text())
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **data}


def save(settings: dict) -> None:
    PATH.write_text(json.dumps(settings, indent=2))


def pending_alerts(settings: dict, cycle_key: str, value: float | None) -> list[int]:
    """Thresholds crossed in this billing cycle that haven't been notified yet; marks them as sent."""
    if value is None:
        return []
    sent = settings["alerted"].get(cycle_key, [])
    new = [t for t in settings["alerts"] if value >= t and t not in sent]
    if new:
        settings["alerted"] = {cycle_key: sent + new}
        save(settings)
    return new
