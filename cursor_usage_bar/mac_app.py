import webbrowser
from datetime import datetime

import rumps

from . import autostart_mac, core, overlay, settings

METRICS = core.METRICS
PIE = ["○", "◔", "◑", "◕", "●"]


def pie(value: float | None) -> str:
    if value is None:
        return "○"
    return PIE[min(4, int(value // 25) + (1 if value % 25 >= 12.5 else 0))]


class CursorUsageApp(rumps.App):
    def __init__(self):
        super().__init__("Cursor Usage", title="… ", quit_button=None)
        self.settings = settings.load()
        self.details = [rumps.MenuItem("Carregando…") for _ in range(6)]
        self.status = rumps.MenuItem("")
        self.metric_items = {
            key: rumps.MenuItem(label, callback=self.choose_metric) for key, label in METRICS.items()
        }
        metric_menu = rumps.MenuItem("Mostrar na barra")
        for item in self.metric_items.values():
            metric_menu.add(item)
        self._mark_metric()

        self.autostart = rumps.MenuItem("Abrir ao iniciar o Mac", callback=self.toggle_autostart)
        self.autostart.state = autostart_mac.is_enabled()
        if autostart_mac.app_bundle() is None:
            self.autostart.set_callback(None)

        self.hud_item = rumps.MenuItem("Gráfico na lateral", callback=self.toggle_hud)
        self.hud_item.state = self.settings.get("overlay", True)
        self.hud = overlay.UsageOverlay(self.settings.get("screen", 1), self.settings.get("capture", "hidden"))
        if self.hud_item.state:
            self.hud.show()

        self.screen_items = {}
        screen_menu = rumps.MenuItem("Tela do gráfico")
        for number, label in overlay.screen_choices():
            item = rumps.MenuItem(label, callback=self.choose_screen)
            self.screen_items[number] = item
            screen_menu.add(item)
        self._mark_screen()

        self.capture_items = {
            "hidden": rumps.MenuItem("Invisível ao compartilhar", callback=self.choose_capture),
            "visible": rumps.MenuItem("Visível ao compartilhar", callback=self.choose_capture),
        }
        capture_menu = rumps.MenuItem("Ao compartilhar a tela")
        for item in self.capture_items.values():
            capture_menu.add(item)
        self._mark_capture()

        self.menu = [
            *self.details,
            None,
            self.status,
            rumps.MenuItem("Atualizar agora", callback=self.refresh, key="r"),
            rumps.MenuItem("Abrir dashboard do Cursor", callback=self.open_dashboard),
            metric_menu,
            self.hud_item,
            screen_menu,
            capture_menu,
            self.autostart,
            None,
            rumps.MenuItem("Sair", callback=rumps.quit_application, key="q"),
        ]
        self.timer = rumps.Timer(self.refresh, self.settings["interval_minutes"] * 60)
        self.timer.start()

    def _mark_metric(self):
        for key, item in self.metric_items.items():
            item.state = key == self.settings["metric"]

    def choose_metric(self, sender):
        self.settings["metric"] = next(k for k, v in METRICS.items() if v == sender.title)
        settings.save(self.settings)
        self._mark_metric()
        self.refresh(None)

    def _mark_screen(self):
        current = 2 if int(self.settings.get("screen", 1)) == 2 else 1
        for number, item in self.screen_items.items():
            item.state = number == current

    def choose_screen(self, sender):
        number = next(n for n, item in self.screen_items.items() if item.title == sender.title)
        self.settings["screen"] = number
        settings.save(self.settings)
        self._mark_screen()
        self.hud.set_screen(number)

    def _mark_capture(self):
        hidden = self.settings.get("capture", "hidden") != "visible"
        self.capture_items["hidden"].state = hidden
        self.capture_items["visible"].state = not hidden

    def choose_capture(self, sender):
        mode = "visible" if sender.title.startswith("Visível") else "hidden"
        self.settings["capture"] = mode
        settings.save(self.settings)
        self._mark_capture()
        self.hud.set_capture(mode)

    def toggle_hud(self, sender):
        sender.state = not sender.state
        self.settings["overlay"] = bool(sender.state)
        settings.save(self.settings)
        if sender.state:
            self.hud.show()
        else:
            self.hud.hide()

    def toggle_autostart(self, sender):
        if sender.state:
            autostart_mac.disable()
        else:
            autostart_mac.enable()
        sender.state = autostart_mac.is_enabled()

    def open_dashboard(self, _):
        webbrowser.open(core.DASHBOARD_URL)

    def refresh(self, _):
        try:
            usage = core.fetch_usage()
        except core.UsageError as exc:
            self.title = "— "
            self.status.title = f"Erro: {exc}"
            self.hud.update(None, str(exc), self.settings["interval_minutes"])
            return

        metric = self.settings["metric"]
        text = core.bar_text(usage, metric)
        if usage.unlimited or metric == "both":
            self.title = text
        else:
            self.title = f"{pie(usage.metric(metric))} {text}"

        lines = core.detail_lines(usage)
        for item, text in zip(self.details, lines + [""] * len(self.details)):
            item.title = text
        every = self.settings["interval_minutes"]
        self.status.title = f"Atualizado às {datetime.now():%H:%M} · a cada {every} min"
        self.hud.update(usage, self.status.title, every)
        self._notify(usage)

    def _notify(self, usage: core.Usage):
        cycle = usage.cycle_start.isoformat() if usage.cycle_start else "unknown"
        for bucket, label in settings.ALERT_BUCKETS.items():
            value = usage.metric(bucket)
            for threshold in settings.pending_alerts(self.settings, cycle, bucket, value):
                try:
                    rumps.notification(
                        "Cursor Usage",
                        f"{label}: passou de {threshold}% do limite",
                        f"Usado: {core.fmt_pct(value)}",
                    )
                except Exception:
                    pass


def hide_dock_icon():
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)


def run():
    hide_dock_icon()
    app = CursorUsageApp()
    app.refresh(None)
    app.run()
