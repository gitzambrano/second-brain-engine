#!/usr/bin/env python3
"""
Entrada humanizada para automação de navegador (Playwright, API síncrona).

Movimento de mouse com curva de Bézier cúbica e duração pela lei de Fitts
(T = a + b·log2(1 + D/W)), ponto de clique com dispersão gaussiana truncada,
micro-tremor, tempo de pressão entre mousedown e mouseup, digitação com pausas
e rolagem em impulsos.

Módulo de biblioteca: sem CLI. Recebe a ``page`` do Playwright; não importa
Playwright.
"""
from __future__ import annotations

import math
import random
import time

_MOUSE = {"x": 200.0, "y": 200.0}


def get_current_mouse_pos() -> tuple[float, float]:
    return (_MOUSE["x"], _MOUSE["y"])


def set_current_mouse_pos(x: float, y: float) -> None:
    _MOUSE["x"], _MOUSE["y"] = float(x), float(y)


def pause(low: float = 0.3, high: float = 0.9) -> None:
    """Ociosidade humana entre passos."""
    time.sleep(random.uniform(low, high))


def fitts_duration(distance: float, target_size: float, a: float = 0.18, b: float = 0.12) -> float:
    """Duração do movimento em segundos, limitada a 0,22–1,25 s."""
    if target_size <= 0:
        target_size = 30.0
    if distance <= 0:
        return 0.1
    duration = (a + b * math.log2(1.0 + distance / target_size)) * random.uniform(0.88, 1.14)
    return max(0.22, min(duration, 1.25))


def sample_target_point(box: dict) -> tuple[float, float]:
    """Ponto de clique dentro da caixa: nem a borda, nem o centro exato."""
    bx, by = box.get("x", 0), box.get("y", 0)
    bw, bh = max(box.get("width", 10), 10), max(box.get("height", 10), 10)
    cx, cy = bx + bw / 2.0, by + bh / 2.0
    for _ in range(10):
        gx, gy = random.gauss(cx, bw * 0.15), random.gauss(cy, bh * 0.15)
        if bx + bw * 0.15 <= gx <= bx + bw * 0.85 and by + bh * 0.15 <= gy <= by + bh * 0.85:
            return gx, gy
    return bx + bw * random.uniform(0.3, 0.7), by + bh * random.uniform(0.3, 0.7)


def cubic_bezier_point(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
    )


def generate_path(start, end, target_size: float = 30.0) -> list[tuple[float, float, float]]:
    """Pontos ``(x, y, espera)`` com perfil de velocidade em sino e arco natural."""
    x0, y0 = start
    x3, y3 = end
    dx, dy = x3 - x0, y3 - y0
    dist = math.hypot(dx, dy)
    if dist < 4.0:
        return [(x3, y3, 0.05)]
    total = fitts_duration(dist, target_size)
    nx, ny = -dy / dist, dx / dist
    deviation = dist * random.uniform(0.08, 0.22) * (1 if random.random() < 0.5 else -1)
    p1 = (x0 + dx * random.uniform(0.2, 0.38) + nx * deviation * random.uniform(0.7, 1.1),
          y0 + dy * random.uniform(0.2, 0.38) + ny * deviation * random.uniform(0.7, 1.1))
    p2 = (x0 + dx * random.uniform(0.62, 0.82) + nx * deviation * random.uniform(0.4, 0.8),
          y0 + dy * random.uniform(0.62, 0.82) + ny * deviation * random.uniform(0.4, 0.8))
    steps = max(12, int(total * random.uniform(55, 75)))
    path = []
    for i in range(1, steps + 1):
        lin = i / steps
        eased = lin * lin * (3.0 - 2.0 * lin)
        bx, by = cubic_bezier_point((x0, y0), p1, p2, (x3, y3), eased)
        tremor = (1.0 - lin * 0.75) * 0.8
        path.append((bx + random.uniform(-tremor, tremor),
                     by + random.uniform(-tremor, tremor),
                     (total / steps) * random.uniform(0.85, 1.15)))
    path[-1] = (x3, y3, random.uniform(0.04, 0.09))
    return path


def move_to(page, x: float, y: float, target_size: float = 35.0) -> None:
    cx, cy = get_current_mouse_pos()
    for px, py, delay in generate_path((cx, cy), (x, y), target_size):
        page.mouse.move(px, py)
        time.sleep(delay)
    set_current_mouse_pos(x, y)


def click_at(page, x: float, y: float, target_size: float = 35.0) -> None:
    move_to(page, x, y, target_size)
    time.sleep(random.uniform(0.06, 0.16))
    page.mouse.down()
    try:
        time.sleep(random.uniform(0.075, 0.145))
    finally:
        page.mouse.up()
    time.sleep(random.uniform(0.08, 0.22))


def human_click(page, target, timeout: float = 12000) -> None:
    """Clique humanizado num locator (ou seletor); cai no clique nativo sem caixa."""
    loc = page.locator(target).first if isinstance(target, str) else target
    loc.wait_for(state="visible", timeout=timeout)
    loc.scroll_into_view_if_needed(timeout=timeout)
    box = loc.bounding_box()
    if not box:
        loc.click(timeout=timeout)
        return
    x, y = sample_target_point(box)
    click_at(page, x, y, min(box.get("width", 30), box.get("height", 30)))


def human_type(page, target, text: str, clear_first: bool = False, timeout: float = 10000) -> None:
    """Digita; textos longos são inseridos de uma vez, como uma colagem."""
    loc = page.locator(target).first if isinstance(target, str) else target
    human_click(page, loc, timeout=timeout)
    if clear_first:
        page.keyboard.press("Control+A")
        time.sleep(random.uniform(0.05, 0.12))
        page.keyboard.press("Backspace")
        time.sleep(random.uniform(0.08, 0.18))
    if len(text) > 60:
        try:
            page.evaluate(
                """([el, val]) => {
                    el.focus();
                    if (el.isContentEditable) {
                        document.execCommand('selectAll', false, null);
                        document.execCommand('insertText', false, val);
                    } else {
                        const proto = el.tagName === 'TEXTAREA'
                            ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                        setter.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""",
                [loc.element_handle(), text],
            )
            time.sleep(random.uniform(0.25, 0.5))
            return
        except Exception:  # noqa: BLE001 - cai para a digitação tecla a tecla
            pass
    for char in text:
        page.keyboard.type(char)
        if char in ".,!?\n":
            time.sleep(random.uniform(0.05, 0.12))
        elif char == " ":
            time.sleep(random.uniform(0.02, 0.06))
        else:
            time.sleep(random.uniform(0.01, 0.035))


def human_scroll(page, delta_y: int, steps: int = 6) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, (delta_y / steps) * random.uniform(0.85, 1.15))
        time.sleep(random.uniform(0.04, 0.09))
    time.sleep(random.uniform(0.1, 0.25))
