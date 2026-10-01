import json
from pathlib import Path

PATH = Path.home() / ".cursor-usage-bar.json"
DEFAULTS = {
    "metric": "both",
    "interval_minutes": 5,
    "alerts": [80, 95],
    "alerted": {},
    "overlay": True,
    "screen": 1,
    "capture": "hidden",
}


def load() -> dict:
    try:
        data = json.loads(PATH.read_text())
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **data}


def save(settings: dict) -> None:
    PATH.write_text(json.dumps(settings, indent=2))


def pending_alerts(settings: dict, cycle: str, bucket: str, value: float | None) -> list[int]:
    """Thresholds crossed in this billing cycle that haven't been notified yet; marks them as sent."""
    if value is None:
        return []
    key = f"{cycle}|{bucket}"
    sent = settings["alerted"].get(key, [])
    new = [t for t in settings["alerts"] if value >= t and t not in sent]
    if new:
        current = {k: v for k, v in settings["alerted"].items() if k.startswith(f"{cycle}|")}
        settings["alerted"] = {**current, key: sent + new}
        save(settings)
    return new


ALERT_BUCKETS = {"auto": "Cursor models", "api": "Other models"}
