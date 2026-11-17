"""A read-only diagnostic view. It renders ControllerState, never hardware."""

import pygame

from .controller import Button, ControllerState, Stick

SIZE = (1120, 790)
BG = (17, 24, 34)
PANEL = (27, 37, 50)
LINE = (65, 82, 102)
TEXT = (230, 237, 244)
MUTED = (155, 173, 193)
GREEN = (92, 225, 171)
GOLD = (249, 200, 107)


class ControllerViewer:
    def __init__(self):
        self.font = pygame.font.SysFont("consolas", 16)
        self.small = pygame.font.SysFont("consolas", 14)
        self.title = pygame.font.SysFont("consolas", 27, bold=True)
        self.flash_until: dict[Button, int] = {}

    def _text(self, surface, text, pos, color=TEXT, font=None):
        surface.blit((font or self.font).render(text, True, color), pos)

    def _button(self, surface, state, button, rect):
        value = state.buttons[button]
        available = button != Button.TOUCHPAD or state.touchpad_available
        fill = GREEN if value.held else PANEL
        pygame.draw.rect(surface, fill, rect, border_radius=9)
        pygame.draw.rect(surface, GOLD if value.toggled else LINE, rect, 2, border_radius=9)
        label = button.value if available else "Touchpad N/A"
        rendered = self.small.render(label, True, BG if value.held else TEXT if available else MUTED)
        surface.blit(rendered, rendered.get_rect(center=rect.center))

    def _stick(self, surface, stick: Stick, center, label):
        pygame.draw.circle(surface, PANEL, center, 48)
        pygame.draw.circle(surface, LINE, center, 48, 2)
        pygame.draw.line(surface, LINE, (center[0]-44, center[1]), (center[0]+44, center[1]))
        pygame.draw.line(surface, LINE, (center[0], center[1]-44), (center[0], center[1]+44))
        pos = (round(center[0] + stick.x * 37), round(center[1] + stick.y * 37))
        pygame.draw.circle(surface, GREEN, pos, 10)
        self._text(surface, label, (center[0]-48, center[1]+56), font=self.small)
        self._text(surface, f"x {stick.x:+.2f}", (center[0]-48, center[1]+77), font=self.small)
        self._text(surface, f"y {stick.y:+.2f}", (center[0]-48, center[1]+96), font=self.small)

    def _trigger(self, surface, value, pos, label):
        self._text(surface, f"{label}  {value:.3f}", pos)
        rect = pygame.Rect(pos[0], pos[1]+26, 180, 12)
        pygame.draw.rect(surface, LINE, rect, border_radius=5)
        if value:
            pygame.draw.rect(surface, GREEN, (rect.x, rect.y, round(180*value), rect.h), border_radius=5)

    def render(self, surface: pygame.Surface, state: ControllerState, status: str, demo: bool = False):
        surface.fill(BG)
        self._text(surface, "PINGUIN / CONTROLLER INPUT", (28, 22), font=self.title)
        self._text(surface, "CONNECTED" if state.connected else "DISCONNECTED", (28, 63), GREEN if state.connected else GOLD)
        self._text(surface, state.name[:68], (185, 63))
        self._text(surface, status[:115], (28, 94), MUTED, self.small)

        pygame.draw.rect(surface, PANEL, (24, 130, 636, 475), border_radius=16)
        self._text(surface, "DUALSHOCK 4 / LIVE STATE", (44, 148), MUTED)
        self._trigger(surface, state.l2, (72, 181), "L2")
        self._trigger(surface, state.r2, (420, 181), "R2")

        positions = {
            Button.L1: (72, 231, 150, 32), Button.R1: (420, 231, 150, 32),
            Button.UP: (117, 287, 58, 34), Button.DOWN: (117, 367, 58, 34),
            Button.LEFT: (57, 327, 58, 34), Button.RIGHT: (177, 327, 58, 34),
            Button.TRIANGLE: (482, 287, 76, 34), Button.CROSS: (482, 367, 76, 34),
            Button.SQUARE: (404, 327, 76, 34), Button.CIRCLE: (560, 327, 76, 34),
            Button.SHARE: (246, 291, 78, 32), Button.OPTIONS: (336, 291, 78, 32),
            Button.TOUCHPAD: (246, 335, 148, 45), Button.PS: (300, 394, 60, 32),
            Button.L3: (178, 568, 80, 30), Button.R3: (405, 568, 80, 30),
        }
        for button, rect in positions.items():
            self._button(surface, state, button, pygame.Rect(rect))
        self._stick(surface, state.left_stick, (218, 443), "LEFT STICK")
        self._stick(surface, state.right_stick, (445, 443), "RIGHT STICK")

        pygame.draw.rect(surface, PANEL, (678, 130, 418, 608), border_radius=16)
        self._text(surface, "BUTTON    HELD  DOWN  UP  TOGGLE", (696, 149), MUTED, self.small)
        now = pygame.time.get_ticks()
        for i, button in enumerate(Button):
            value = state.buttons[button]
            if value.pressed or value.released:
                self.flash_until[button] = now + 170
            y = 181 + i*26
            if self.flash_until.get(button, 0) > now:
                pygame.draw.rect(surface, (43, 63, 77), (690, y-2, 397, 24), border_radius=4)
            name = button.value if button != Button.TOUCHPAD or state.touchpad_available else "Touch N/A"
            self._text(surface, f"{name:<10}", (696, y), TEXT, self.small)
            for x, active in [(800, value.held), (852, value.pressed), (895, value.released), (951, value.toggled)]:
                self._text(surface, "ON" if active else "--", (x, y), GREEN if active else MUTED, self.small)
        self._text(surface, "DOWN / UP last one update.", (696, 665), MUTED, self.small)
        self._text(surface, "Row flash lasts 170ms for visibility.", (696, 687), MUTED, self.small)
        self._text(surface, f"Snapshot {state.sequence}", (696, 709), MUTED, self.small)

        self._text(surface, "Green fill = held | Gold outline = toggled", (28, 624), MUTED, self.small)
        self._text(surface, "Toggle flips once per press; disconnect clears all.", (28, 646), MUTED, self.small)
        self._text(surface, "Sticks: -1..+1, +Y down | Triggers: 0..1", (28, 668), MUTED, self.small)
        if demo:
            lines = [
                "DEMO  WASD: left stick | T/F/G/L: right stick",
                "J/K/H/U: Cross/Circle/Square/Triangle | Arrows: D-pad",
                "Q/E: L1/R1  Z/C: L2/R2  1/2: L3/R3",
                "Tab: Share  Enter: Options  P: PS  Space: Touchpad",
            ]
        else:
            lines = ["Connect a PS4 controller to inspect its inputs.",
                     "Touchpad shows click only, when exposed by SDL.",
                     "No radio commands are sent by this viewer.", "Esc: close"]
        for i, line in enumerate(lines):
            self._text(surface, line, (28, 695+i*21), GOLD if demo and i == 0 else MUTED, self.small)
        self._text(surface, "INPUT DIAGNOSTICS ONLY | Esc to close", (695, 757), MUTED, self.small)
