"""Small semicircle HUD pinned to the right edge of a chosen screen."""

import sys
from pathlib import Path

import objc
from AppKit import (
    NSAppearanceNameAqua,
    NSAppearanceNameDarkAqua,
    NSAttributedString,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSEvent,
    NSFloatingWindowLevel,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSMakeRect,
    NSMutableParagraphStyle,
    NSPanel,
    NSParagraphStyleAttributeName,
    NSPointInRect,
    NSScreen,
    NSWindowSharingNone,
    NSTrackingArea,
    NSTrackingActiveAlways,
    NSTrackingInVisibleRect,
    NSTrackingMouseEnteredAndExited,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSObject, NSURL

_coretext = objc.loadBundle("CoreText", {}, "/System/Library/Frameworks/CoreText.framework")
objc.loadBundleFunctions(_coretext, globals(), [("CTFontManagerRegisterFontsForURL", b"Z@i^@")])

from . import core

SEMI_R = 22
SEMI_R_OPEN = 34
PANEL_W = 300
EXPANDED_H = 276
CAPTURE_HIDDEN = "hidden"
CAPTURE_VISIBLE = "visible"
# Leemia gutter is 1.25rem. Panel radius follows the site's small corners.
GUTTER = 20
PANEL_RADIUS = 4

# Light is the site default. Dark matches html[data-theme="dark"].
LIGHT = {
    "ink": "#f2f5f6",
    "line": "#c9d3d8",
    "bone": "#0b1216",
    "dim": "#5a6b73",
    "cyan": "#0f9bb8",
}
DARK = {
    "ink": "#05070a",
    "line": "#171d24",
    "bone": "#f2f5f6",
    "dim": "#9aa7ae",
    "cyan": "#34c3dd",
}


def _color(hex_color):
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 1)


def _fonts_dir():
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "assets" / "fonts"
    if bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parent.parent / "assets" / "fonts"


def ensure_fonts():
    if getattr(ensure_fonts, "done", False):
        return
    folder = _fonts_dir()
    for font in folder.glob("*.ttf"):
        CTFontManagerRegisterFontsForURL(NSURL.fileURLWithPath_(str(font)), 1, None)
    ensure_fonts.done = True


def _font(role, size):
    """role: sans, medium, mono. Faces are the ones the Leemia site loads."""
    ensure_fonts()
    names = {
        "sans": "SpaceGrotesk-Regular",
        "medium": "SpaceGrotesk-Medium",
        "mono": "JetBrainsMono-Regular",
    }
    font = NSFont.fontWithName_size_(names[role], size)
    if font is not None:
        return font
    if role == "mono":
        return NSFont.monospacedSystemFontOfSize_weight_(size, 5)
    return NSFont.systemFontOfSize_weight_(size, 5 if role == "medium" else 4)


def palette_for(appearance):
    match = appearance.bestMatchFromAppearancesWithNames_([NSAppearanceNameAqua, NSAppearanceNameDarkAqua])
    colors = DARK if match == NSAppearanceNameDarkAqua else LIGHT
    return {key: _color(value) for key, value in colors.items()}


def _text(value, x, y, w, h, font, color, align="left", kern=0):
    style = NSMutableParagraphStyle.alloc().init()
    style.setAlignment_({"left": 0, "center": 1, "right": 2}[align])
    attrs = {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: color,
        NSParagraphStyleAttributeName: style,
    }
    if kern:
        attrs["NSKern"] = kern
    NSAttributedString.alloc().initWithString_attributes_(str(value), attrs).drawInRect_(
        NSMakeRect(x, y, w, h)
    )


def collapsed_size():
    reach = SEMI_R + 4
    return reach, reach * 2


def expanded_size():
    reach = SEMI_R_OPEN + 8
    return PANEL_W + 10 + reach, EXPANDED_H


def screen_choices():
    """(index, menu label) for the first two displays. Index is 1-based."""
    screens = list(NSScreen.screens() or [])
    choices = []
    for number in (1, 2):
        if number - 1 < len(screens):
            choices.append((number, f"Tela {number} · {screens[number - 1].localizedName()}"))
        else:
            choices.append((number, f"Tela {number} (desconectada)"))
    return choices


def _half_arc(cx, cy, radius, start_sweep, sweep):
    path = NSBezierPath.bezierPath()
    # -90° is 12 o'clock. Clockwise in this flipped view runs down the left side,
    # which is the half that stays on screen when the center sits on the right edge.
    path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
        (cx, cy), radius, -90 - start_sweep, -90 - start_sweep - sweep, True
    )
    return path


def _half_ring(cx, cy, radius, width, fraction, stroke, track_color):
    track = _half_arc(cx, cy, radius, 0, 180)
    track.setLineWidth_(width)
    track.setLineCapStyle_(0)
    track_color.set()
    track.stroke()
    if not fraction or fraction <= 0:
        return
    arc = _half_arc(cx, cy, radius, 0, 180 * min(fraction, 1))
    arc.setLineWidth_(width)
    arc.setLineCapStyle_(1)
    stroke.set()
    arc.stroke()


class HudView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(HudView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._usage = None
        self._status = "carregando…"
        self._interval = 5
        self._expanded = False
        self._area = None
        self.on_hover = None
        return self

    def isFlipped(self):
        return True

    def updateTrackingAreas(self):
        objc.super(HudView, self).updateTrackingAreas()
        if self._area is not None:
            self.removeTrackingArea_(self._area)
        self._area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(),
            NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways | NSTrackingInVisibleRect,
            self,
            None,
        )
        self.addTrackingArea_(self._area)

    def mouseEntered_(self, _event):
        NSObject.cancelPreviousPerformRequestsWithTarget_(self)
        if self.on_hover:
            self.on_hover(True)

    def mouseExited_(self, _event):
        self.performSelector_withObject_afterDelay_("collapseIfOutside:", None, 0.12)

    def collapseIfOutside_(self, _sender):
        window = self.window()
        if window is not None and NSPointInRect(NSEvent.mouseLocation(), window.frame()):
            return
        if self.on_hover:
            self.on_hover(False)

    def drawRect_(self, _rect):
        bounds = self.bounds()
        width, height = bounds.size.width, bounds.size.height
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(bounds)

        colors = palette_for(self.effectiveAppearance())
        radius = SEMI_R_OPEN if self._expanded else SEMI_R
        reserve = radius + 10
        if self._expanded:
            draw_panel(
                8, 8, width - reserve - 10, height - 16,
                self._usage, self._status, self._interval, colors,
            )
        draw_semi(width, height / 2, radius, self._usage, self._expanded, colors)


def draw_semi(right, cy, radius, usage, expanded, colors):
    """Semicircle whose center sits on the right edge, so only the left half is visible."""
    disc = _half_arc(right, cy, radius, 0, 180)
    disc.closePath()
    colors["ink"].set()
    disc.fill()
    rim = _half_arc(right, cy, radius, 0, 180)
    rim.setLineWidth_(1)
    colors["line"].set()
    rim.stroke()

    auto = None if usage is None else usage.auto_pct
    api = None if usage is None else usage.api_pct
    width = 4 if expanded else 3
    # Outer arc is Other models (bone). Inner arc is Cursor models (cyan).
    _half_ring(right, cy, radius - 5, width, 0 if api is None else api / 100, colors["bone"], colors["line"])
    _half_ring(right, cy, radius - 11, width, 0 if auto is None else auto / 100, colors["cyan"], colors["line"])


def draw_bar(x, y, w, h, fraction, color, track_color):
    track = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(NSMakeRect(x, y, w, h), 1, 1)
    track_color.set()
    track.fill()
    if fraction > 0:
        fill = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(x, y, max(h, w * fraction), h), 1, 1
        )
        color.set()
        fill.fill()


def _rule(x, y, w, color):
    path = NSBezierPath.bezierPath()
    path.moveToPoint_((x, y))
    path.lineToPoint_((x + w, y))
    path.setLineWidth_(1)
    color.set()
    path.stroke()


def draw_panel(x, y, w, h, usage, status, interval, colors):
    panel = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(x, y, w, h), PANEL_RADIUS, PANEL_RADIUS
    )
    colors["ink"].set()
    panel.fill()
    panel.setLineWidth_(1)
    colors["line"].set()
    panel.stroke()

    left = x + GUTTER
    top = y + GUTTER
    inner = w - GUTTER * 2
    mono = _font("mono", 11)
    sans = _font("sans", 13)
    medium = _font("medium", 13)
    _text("CURSOR  /  USO", left, top, inner - 72, 14, mono, colors["dim"], kern=1.6)
    plan = (usage.membership or "").upper() if usage else ""
    _text(plan, left + inner - 72, top, 72, 14, mono, colors["cyan"], "right", kern=1.4)

    line_y = top + 22
    _rule(left, line_y, inner, colors["line"])

    rows = [
        ("CURSOR MODELS", None if usage is None else usage.auto_pct, colors["cyan"]),
        ("OTHER MODELS", None if usage is None else usage.api_pct, colors["bone"]),
        ("TOTAL", None if usage is None else usage.total_pct, colors["dim"]),
    ]
    row_y = line_y + 14
    for label, pct, tint in rows:
        _text(label, left, row_y, inner - 58, 14, mono, colors["dim"], kern=1.1)
        _text(core.fmt_pct(pct), left + inner - 58, row_y - 1, 58, 16, medium, tint, "right")
        draw_bar(left, row_y + 18, inner, 3, 0 if pct is None else pct / 100, tint, colors["line"])
        row_y += 36

    if usage and usage.cycle_start and usage.cycle_end:
        cycle = f"CICLO  {usage.cycle_start:%d/%m}  →  {usage.cycle_end:%d/%m}"
        days = usage.days_left()
        extra = f"{days} DIAS" if days is not None else ""
    else:
        cycle, extra = "CICLO  —", ""
    _text(cycle, left, row_y + 4, inner - 72, 14, sans, colors["bone"])
    _text(extra, left + inner - 72, row_y + 4, 72, 14, medium, colors["cyan"], "right")

    if usage is None:
        demand = status
    elif usage.on_demand_enabled:
        limit = core.fmt_cents(usage.on_demand_limit) if usage.on_demand_limit else "sem limite"
        demand = f"ON-DEMAND  {core.fmt_cents(usage.on_demand_used)}  /  {limit}"
    else:
        demand = "ON-DEMAND  DESATIVADO"
    _text(demand, left, row_y + 22, inner, 14, sans, colors["dim"])

    foot = row_y + 44
    _rule(left, foot, inner, colors["line"])
    footer = status if usage is not None else f"tenta de novo a cada {interval} min"
    _text(footer, left, foot + 8, inner, 14, mono, colors["dim"])


class UsageOverlay:
    def __init__(self, screen=1, capture=CAPTURE_HIDDEN):
        self.screen_index = 1 if int(screen) != 2 else 2
        self.capture = capture if capture in (CAPTURE_HIDDEN, CAPTURE_VISIBLE) else CAPTURE_HIDDEN
        self._expanded = False
        self._place_anchor()
        frame = self._frame(False)
        self.view = HudView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, frame.size.height))
        self.view.setAutoresizingMask_(18)
        self.view.on_hover = self._hover
        self.panel = self._make_panel(frame)

    def _display(self):
        screens = list(NSScreen.screens() or [])
        if not screens:
            return NSScreen.mainScreen()
        index = self.screen_index - 1
        if index >= len(screens):
            index = 0
        return screens[index]

    def _place_anchor(self):
        vis = self._display().visibleFrame()
        self.anchor_right = vis.origin.x + vis.size.width
        self.anchor_mid = vis.origin.y + vis.size.height / 2

    def _frame(self, expanded):
        w, h = expanded_size() if expanded else collapsed_size()
        return NSMakeRect(self.anchor_right - w, self.anchor_mid - h / 2, w, h)

    def _apply_frame(self):
        self.panel.setFrame_display_(self._frame(self._expanded), True)

    def _make_panel(self, frame):
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setContentView_(self.view)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(False)
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setHidesOnDeactivate_(False)
        panel.setFloatingPanel_(True)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
        # SharingNone sticks for the life of the window, so the visible mode
        # keeps the default instead of trying to switch back.
        if self.capture != CAPTURE_VISIBLE:
            panel.setSharingType_(NSWindowSharingNone)
        return panel

    def set_screen(self, number):
        self.screen_index = 2 if int(number) == 2 else 1
        self._expanded = False
        self.view._expanded = False
        self._place_anchor()
        self._apply_frame()

    def set_capture(self, capture):
        new = CAPTURE_VISIBLE if capture == CAPTURE_VISIBLE else CAPTURE_HIDDEN
        if new == self.capture:
            return
        self.capture = new
        visible = self.panel.isVisible()
        self.panel.orderOut_(None)
        self.panel = self._make_panel(self._frame(self._expanded))
        if visible:
            self.panel.orderFrontRegardless()

    def _hover(self, expanded):
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.view._expanded = expanded
        self._apply_frame()

    def update(self, usage, status, interval):
        self.view._usage = usage
        self.view._status = status
        self.view._interval = interval
        self.view.setNeedsDisplay_(True)

    def show(self):
        self._place_anchor()
        self._apply_frame()
        self.panel.orderFrontRegardless()

    def hide(self):
        self.panel.orderOut_(None)
