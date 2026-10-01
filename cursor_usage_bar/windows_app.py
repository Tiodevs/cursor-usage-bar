import threading
import webbrowser
from datetime import datetime

import pystray
from PIL import Image, ImageDraw, ImageFont

from . import core, settings

COLORS = {"ok": "#2e7d32", "warning": "#f9a825", "critical": "#c62828", "unknown": "#616161"}
METRICS = {"total": "Total", "auto": "Auto + Composer", "api": "API"}


def _font(size: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def render_icon(value: float | None) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=12, fill=COLORS[core.level(value)])
    text = "—" if value is None else str(min(99, round(value)))
    font = _font(40 if len(text) < 2 else 34)
    draw.text((size / 2, size / 2), text, fill="white", font=font, anchor="mm")
    return img


class TrayApp:
    def __init__(self):
        self.settings = settings.load()
        self.lines = ["Carregando…"]
        self.status = ""
        self.stop = threading.Event()
        self.icon = pystray.Icon("cursor-usage-bar", render_icon(None), "Cursor Usage", self._menu())

    def _menu(self):
        detail_items = [
            pystray.MenuItem(lambda _, i=i: self.lines[i] if i < len(self.lines) else "", None,
                             enabled=False, visible=lambda _, i=i: i < len(self.lines))
            for i in range(6)
        ]
        metric_items = [
            pystray.MenuItem(label, self._choose(key), radio=True,
                             checked=lambda _, k=key: self.settings["metric"] == k)
            for key, label in METRICS.items()
        ]
        return pystray.Menu(
            *detail_items,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda _: self.status, None, enabled=False),
            pystray.MenuItem("Atualizar agora", lambda: self.refresh(), default=True),
            pystray.MenuItem("Abrir dashboard do Cursor", lambda: webbrowser.open(core.DASHBOARD_URL)),
            pystray.MenuItem("Mostrar no ícone", pystray.Menu(*metric_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self.quit),
        )

    def _choose(self, key):
        def handler():
            self.settings["metric"] = key
            settings.save(self.settings)
            self.refresh()
        return handler

    def refresh(self):
        try:
            usage = core.fetch_usage()
        except core.UsageError as exc:
            self.icon.icon = render_icon(None)
            self.icon.title = f"Cursor Usage — {exc}"
            self.status = f"Erro: {exc}"
            self.icon.update_menu()
            return

        value = None if usage.unlimited else usage.metric(self.settings["metric"])
        self.lines = core.detail_lines(usage)
        self.status = f"Atualizado às {datetime.now():%H:%M}"
        self.icon.icon = render_icon(value)
        # Windows caps tray tooltips at 127 characters.
        self.icon.title = "\n".join(self.lines[:4])[:127]
        self.icon.update_menu()
        self._notify(usage)

    def _notify(self, usage: core.Usage):
        cycle = usage.cycle_start.isoformat() if usage.cycle_start else "unknown"
        for threshold in settings.pending_alerts(self.settings, cycle, usage.total_pct):
            try:
                self.icon.notify(f"Total usado: {core.fmt_pct(usage.total_pct)}",
                                 f"Você passou de {threshold}% do limite")
            except Exception:
                pass

    def _loop(self, icon):
        icon.visible = True
        while not self.stop.is_set():
            self.refresh()
            self.stop.wait(self.settings["interval_minutes"] * 60)

    def quit(self):
        self.stop.set()
        self.icon.stop()

    def run(self):
        self.icon.run(setup=self._loop)


def run():
    TrayApp().run()
