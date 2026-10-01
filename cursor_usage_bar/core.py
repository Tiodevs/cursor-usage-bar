import base64
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

USAGE_URL = "https://cursor.com/api/usage-summary"
DASHBOARD_URL = "https://cursor.com/dashboard?tab=usage"


class UsageError(Exception):
    pass


class AuthError(UsageError):
    pass


def state_db_path() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def read_access_token() -> str:
    path = state_db_path()
    if not path.exists():
        raise AuthError("Cursor não encontrado nesta máquina")
    # Read-only URI: the DB is large and held open by Cursor, so never write or lock it.
    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            row = conn.execute(
                "SELECT value FROM ItemTable WHERE key = 'cursorAuth/accessToken'"
            ).fetchone()
    except sqlite3.Error as exc:
        raise UsageError(f"Falha ao ler o banco do Cursor: {exc}") from exc
    if not row or not row[0]:
        raise AuthError("Faça login no Cursor")
    return row[0]


def user_id_from_token(token: str) -> str:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        sub = json.loads(base64.urlsafe_b64decode(payload))["sub"]
    except (IndexError, ValueError, KeyError) as exc:
        raise AuthError("Token do Cursor inválido") from exc
    return sub.split("|")[-1]


def fetch_usage_summary(timeout: float = 10) -> dict:
    token = read_access_token()
    cookie = f"WorkosCursorSessionToken={user_id_from_token(token)}%3A%3A{token}"
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Cookie": cookie,
            "Accept": "application/json",
            "User-Agent": "cursor-usage-bar",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthError("Sessão expirada — abra o Cursor") from exc
        raise UsageError(f"Erro HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise UsageError("Sem conexão") from exc
    except ValueError as exc:
        raise UsageError("Resposta inesperada da API") from exc


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class Usage:
    total_pct: float | None
    auto_pct: float | None
    api_pct: float | None
    membership: str | None
    unlimited: bool
    cycle_start: datetime | None
    cycle_end: datetime | None
    on_demand_enabled: bool
    on_demand_used: float | None
    on_demand_limit: float | None

    @classmethod
    def from_api(cls, data: dict) -> "Usage":
        individual = data.get("individualUsage") or {}
        plan = individual.get("plan") or {}
        on_demand = individual.get("onDemand") or {}
        return cls(
            total_pct=plan.get("totalPercentUsed"),
            auto_pct=plan.get("autoPercentUsed"),
            api_pct=plan.get("apiPercentUsed"),
            membership=data.get("membershipType"),
            unlimited=bool(data.get("isUnlimited")),
            cycle_start=_parse_date(data.get("billingCycleStart")),
            cycle_end=_parse_date(data.get("billingCycleEnd")),
            on_demand_enabled=bool(on_demand.get("enabled")),
            on_demand_used=on_demand.get("used"),
            on_demand_limit=on_demand.get("limit"),
        )

    def metric(self, name: str) -> float | None:
        return {"total": self.total_pct, "auto": self.auto_pct, "api": self.api_pct}.get(name)

    def days_left(self) -> int | None:
        if not self.cycle_end:
            return None
        return max(0, (self.cycle_end - datetime.now(timezone.utc)).days)


def fetch_usage() -> Usage:
    return Usage.from_api(fetch_usage_summary())


def fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}%"


def fmt_cents(value: float | None) -> str:
    return "—" if value is None else f"US$ {value / 100:.2f}"


def level(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= 90:
        return "critical"
    if value >= 70:
        return "warning"
    return "ok"


def detail_lines(usage: Usage) -> list[str]:
    lines = [
        f"Total: {fmt_pct(usage.total_pct)} usado",
        f"Auto + Composer: {fmt_pct(usage.auto_pct)} usado",
        f"API (modelos nomeados): {fmt_pct(usage.api_pct)} usado",
    ]
    if usage.cycle_start and usage.cycle_end:
        lines.append(
            f"Ciclo: {usage.cycle_start:%d/%m} → {usage.cycle_end:%d/%m} "
            f"({usage.days_left()} dias restantes)"
        )
    if usage.on_demand_enabled:
        limit = fmt_cents(usage.on_demand_limit) if usage.on_demand_limit else "sem limite"
        lines.append(f"On-demand: {fmt_cents(usage.on_demand_used)} de {limit}")
    else:
        lines.append("On-demand: desativado")
    if usage.membership:
        lines.append(f"Plano: {usage.membership}")
    return lines
