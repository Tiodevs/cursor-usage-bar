"""Floating circular HUD pinned to the right edge of the screen."""

import math

import objc
from AppKit import (
    NSAttributedString,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSEvent,
    NSFloatingWindowLevel,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSMakeRect,
    NSMutableParagraphStyle,
    NSPanel,
    NSParagraphStyleAttributeName,
    NSPointInRect,
    NSScreen,
    NSShadow,
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
from Foundation import NSObject

from . import core

COLLAPSED = 148
PANEL_W = 276
EXPANDED_W = PANEL_W + COLLAPSED + 6
EXPANDED_H = 252
SCREEN_MARGIN = 10

CYAN = (0.30, 0.93, 1.0)
VIOLET = (0.74, 0.48, 1.0)
INK = (0.90, 0.95, 1.0)
DIM = (0.55, 0.66, 0.78)
GLASS = (0.03, 0.05, 0.09, 0.94)


def _color(*rgba):
    r, g, b, *a = rgba
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a[0] if a else 1)


def _font(size, bold=False):
    name = "Menlo-Bold" if bold else "Menlo"
    font = NSFont.fontWithName_size_(name, size)
    return font or NSFont.monospacedSystemFontOfSize_weight_(size, 8 if bold else 5)


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


def _ring(cx, cy, radius, width, fraction, stroke, track):
    track_path = NSBezierPath.bezierPath()
    track_path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
        (cx, cy), radius, 0, 360, True
    )
    track_path.setLineWidth_(width)
    track.set()
    track_path.stroke()
    if not fraction or fraction <= 0:
        return
    sweep = 360 * min(fraction, 1)
    arc = NSBezierPath.bezierPath()
    # -90° is 12 o'clock in this flipped view; counterclockwise draws clockwise on screen.
    arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
        (cx, cy), radius, -90, -90 + sweep, False
    )
    arc.setLineWidth_(width)
    arc.setLineCapStyle_(1)
    ctx = NSGraphicsContext.currentContext()
    ctx.saveGraphicsState()
    shadow = NSShadow.alloc().init()
    shadow.setShadowOffset_((0, 0))
    shadow.setShadowBlurRadius_(8)
    shadow.setShadowColor_(stroke.colorWithAlphaComponent_(0.85))
    shadow.set()
    stroke.set()
    arc.stroke()
    ctx.restoreGraphicsState()


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

        gauge = COLLAPSED
        gx = width - gauge
        gy = (height - gauge) / 2
        if self._expanded:
            draw_panel(6, 8, width - gauge - 12, height - 16, self._usage, self._status, self._interval)
        draw_gauge(gx, gy, gauge, self._usage)


def draw_gauge(x, y, side, usage):
    cx, cy = x + side / 2, y + side / 2
    radius = side / 2 - 8
    _color(*GLASS).set()
    disc = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(cx - radius, cy - radius, radius * 2, radius * 2))
    disc.fill()

    auto = None if usage is None else usage.auto_pct
    api = None if usage is None else usage.api_pct
    _ring(cx, cy, radius - 10, 7, 0 if api is None else api / 100, _color(*VIOLET), _color(1, 1, 1, 0.08))
    _ring(cx, cy, radius - 22, 7, 0 if auto is None else auto / 100, _color(*CYAN), _color(1, 1, 1, 0.08))
    draw_ticks(cx, cy, radius - 2)

    _color(*CYAN, 0.9).set()
    NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(cx - 2, cy - 2, 4, 4)).fill()
    _text(f"C  {core.fmt_pct(auto)}", cx - 40, cy - 17, 80, 14, _font(10, True), _color(*CYAN), "center")
    _text(f"API {core.fmt_pct(api)}", cx - 40, cy + 1, 80, 14, _font(10, True), _color(*VIOLET), "center")

    rim = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(cx - radius, cy - radius, radius * 2, radius * 2))
    rim.setLineWidth_(1)
    _color(*CYAN, 0.35).set()
    rim.stroke()


def draw_ticks(cx, cy, radius):
    for i in range(48):
        major = i % 6 == 0
        ang = math.radians(i * 7.5 - 90)
        inner = radius - (5 if major else 2.5)
        path = NSBezierPath.bezierPath()
        path.moveToPoint_((cx + math.cos(ang) * inner, cy + math.sin(ang) * inner))
        path.lineToPoint_((cx + math.cos(ang) * radius, cy + math.sin(ang) * radius))
        path.setLineWidth_(1.2 if major else 0.6)
        _color(0.55, 0.85, 1, 0.55 if major else 0.22).set()
        path.stroke()


def draw_bar(x, y, w, h, fraction, color):
    track = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(NSMakeRect(x, y, w, h), h / 2, h / 2)
    _color(1, 1, 1, 0.08).set()
    track.fill()
    if fraction > 0:
        fill = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(x, y, max(h, w * fraction), h), h / 2, h / 2
        )
        color.set()
        fill.fill()


def draw_panel(x, y, w, h, usage, status, interval):
    panel = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(NSMakeRect(x, y, w, h), 16, 16)
    _color(*GLASS).set()
    panel.fill()
    panel.setLineWidth_(1)
    _color(*CYAN, 0.28).set()
    panel.stroke()

    pad = 16
    left, top = x + pad, y + 14
    inner = w - pad * 2
    _text("CURSOR  //  USO", left, top, inner - 70, 16, _font(10, True), _color(*CYAN), kern=1.2)
    plan = (usage.membership or "").upper() if usage else ""
    _text(plan, left + inner - 70, top, 70, 16, _font(10, True), _color(*VIOLET), "right")

    line_y = top + 24
    rule = NSBezierPath.bezierPath()
    rule.moveToPoint_((left, line_y))
    rule.lineToPoint_((left + inner, line_y))
    rule.setLineWidth_(1)
    _color(*CYAN, 0.25).set()
    rule.stroke()

    rows = [
        ("CURSOR MODELS", None if usage is None else usage.auto_pct, CYAN),
        ("OTHER MODELS", None if usage is None else usage.api_pct, VIOLET),
        ("TOTAL", None if usage is None else usage.total_pct, INK),
    ]
    row_y = line_y + 12
    for label, pct, tint in rows:
        _text(label, left, row_y, inner - 56, 14, _font(9), _color(*DIM))
        _text(core.fmt_pct(pct), left + inner - 56, row_y, 56, 14, _font(12, True), _color(*tint), "right")
        draw_bar(left, row_y + 16, inner, 4, 0 if pct is None else pct / 100, _color(*tint))
        row_y += 32

    if usage and usage.cycle_start and usage.cycle_end:
        cycle = f"CICLO   {usage.cycle_start:%d/%m}  →  {usage.cycle_end:%d/%m}"
        days = usage.days_left()
        extra = f"{days} DIAS" if days is not None else ""
    else:
        cycle, extra = "CICLO   —", ""
    _text(cycle, left, row_y + 2, inner - 64, 14, _font(9), _color(*INK))
    _text(extra, left + inner - 64, row_y + 2, 64, 14, _font(9, True), _color(*CYAN), "right")

    if usage is None:
        demand = status
    elif usage.on_demand_enabled:
        limit = core.fmt_cents(usage.on_demand_limit) if usage.on_demand_limit else "sem limite"
        demand = f"ON-DEMAND   {core.fmt_cents(usage.on_demand_used)}  /  {limit}"
    else:
        demand = "ON-DEMAND   DESATIVADO"
    _text(demand, left, row_y + 20, inner, 14, _font(9), _color(*DIM))

    foot = row_y + 42
    rule2 = NSBezierPath.bezierPath()
    rule2.moveToPoint_((left, foot))
    rule2.lineToPoint_((left + inner, foot))
    _color(*CYAN, 0.18).set()
    rule2.stroke()
    footer = status if usage is not None else f"tenta de novo a cada {interval} min"
    _text(footer, left, foot + 6, inner, 14, _font(8), _color(*DIM))


class UsageOverlay:
    def __init__(self):
        vis = NSScreen.mainScreen().visibleFrame()
        self.anchor_right = vis.origin.x + vis.size.width - SCREEN_MARGIN
        self.anchor_mid = vis.origin.y + vis.size.height / 2
        self._expanded = False
        frame = self._frame(False)
        self.view = HudView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, frame.size.height))
        self.view.setAutoresizingMask_(18)
        self.view.on_hover = self._hover
        self.panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        self.panel.setContentView_(self.view)
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(NSColor.clearColor())
        self.panel.setHasShadow_(False)
        self.panel.setLevel_(NSFloatingWindowLevel)
        self.panel.setHidesOnDeactivate_(False)
        self.panel.setFloatingPanel_(True)
        self.panel.setBecomesKeyOnlyIfNeeded_(True)
        self.panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
    def _frame(self, expanded):
        w, h = (EXPANDED_W, EXPANDED_H) if expanded else (COLLAPSED, COLLAPSED)
        return NSMakeRect(self.anchor_right - w, self.anchor_mid - h / 2, w, h)

    def _hover(self, expanded):
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.view._expanded = expanded
        self.panel.setFrame_display_(self._frame(expanded), True)

    def update(self, usage, status, interval):
        self.view._usage = usage
        self.view._status = status
        self.view._interval = interval
        self.view.setNeedsDisplay_(True)

    def show(self):
        self.panel.orderFrontRegardless()

    def hide(self):
        self.panel.orderOut_(None)
