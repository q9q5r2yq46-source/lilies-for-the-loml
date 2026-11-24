"""A small, rotating terminal bouquet for Seth and Megan.

This is a standalone, standard-library-only terminal renderer.  It samples
simple 3D surfaces into a character grid and uses a depth buffer to decide
which character is visible at each terminal cell.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
import time


FPS = 20
SPIN_SPEED = 0.50
CAMERA_DISTANCE = 4.0
TILT = 0.25
PIVOT_Y = 0.2

FROM_LINE = "From: Seth"
TO_LINE = "To: Megan"
SUBJECT = "I love you."

BLUE_LILY = [27, 33, 39, 45, 51, 75, 81, 117, 123, 159, 195]
PINK_LILY = [125, 162, 168, 169, 175, 205, 211, 212, 218, 224]
STAMEN = [178, 214, 220, 226]
STEM = [22, 28, 34, 35, 40, 70, 76, 112]
WRAP = [60, 96, 102, 138, 180, 216, 223, 230]
PETAL_MARKS = ".:-=+*#%@"

LIGHT = (-0.45, 0.72, 0.62)
LIGHT_LENGTH = math.sqrt(sum(component * component for component in LIGHT))
LIGHT = tuple(component / LIGHT_LENGTH for component in LIGHT)


def normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(component * component for component in vector))
    if length < 1e-9:
        return (0.0, 1.0, 0.0)
    return tuple(component / length for component in vector)


def add_point(points, position, normal, palette, tone=0.0, two_sided=True, character=None):
    points.append((position, normal, palette, tone, two_sided, character))


def build_lily(flowers, center, palette, seed):
    # Lily heads stay face-on and readable while their 3D centers orbit.
    flowers.append((center, palette, seed * 0.61))


def build_scene():
    points = []
    flowers = []
    neck = (0.0, -0.18, 0.0)
    # The heads wrap around the bouquet at uneven angles, heights, and radii.
    # Alternating colors gives exactly six blue and six pink lilies.
    layout = (
        (0.08, 1.03, 0.78, BLUE_LILY),
        (0.59, 1.38, 0.68, PINK_LILY),
        (1.07, 0.82, 0.84, BLUE_LILY),
        (1.55, 1.19, 0.64, PINK_LILY),
        (2.02, 1.47, 0.75, BLUE_LILY),
        (2.51, 0.94, 0.88, PINK_LILY),
        (3.00, 1.31, 0.66, BLUE_LILY),
        (3.53, 0.75, 0.82, PINK_LILY),
        (4.02, 1.17, 0.72, BLUE_LILY),
        (4.54, 1.44, 0.63, PINK_LILY),
        (5.03, 0.88, 0.87, BLUE_LILY),
        (5.56, 1.26, 0.73, PINK_LILY),
    )
    heads = []
    for azimuth, height, radius, palette in layout:
        center = (radius * math.sin(azimuth), height, radius * math.cos(azimuth))
        heads.append((center, palette, azimuth))

    for index, (head, palette, azimuth) in enumerate(heads):
        # Stems curve gently from the tied bouquet neck to each flower.
        for step in range(28):
            t = step / 27
            bend = 0.035 * math.sin(math.pi * t + index)
            position = (
                neck[0] + (head[0] - neck[0]) * t + bend,
                neck[1] + (head[1] - neck[1]) * t,
                neck[2] + (head[2] - neck[2]) * t,
            )
            add_point(points, position, (0.2, 0.6, 0.2), STEM, -0.04, True, "|")

        build_lily(flowers, head, palette, index)

    # A tapered paper wrap, sampled as rings so it can rotate with the flowers.
    y_bottom, y_top = -0.34, 0.35
    r_bottom, r_top = 0.09, 0.54
    slope = (r_top - r_bottom) / (y_top - y_bottom)
    for ring in range(52):
        t = ring / 51
        y = y_bottom + (y_top - y_bottom) * t
        radius = r_bottom + (r_top - r_bottom) * t
        for around in range(112):
            angle = math.tau * around / 112
            ripple = 0.012 * math.sin(7 * angle + 0.4)
            r = radius + ripple
            normal = normalize((math.cos(angle), -slope, math.sin(angle)))
            tone = -0.24 if math.sin(6 * angle) > 0.65 else 0.0
            add_point(points, (r * math.cos(angle), y, r * math.sin(angle)), normal, WRAP, tone, False, None)

    return points, flowers


def transform_and_project(position, angle, cols, view_rows):
    x, y, z = position
    ca, sa = math.cos(angle), math.sin(angle)
    rotated_x = x * ca - z * sa
    rotated_z = x * sa + z * ca

    tilt_c, tilt_s = math.cos(TILT), math.sin(TILT)
    y -= PIVOT_Y
    tilted_y = y * tilt_c - rotated_z * tilt_s
    depth = y * tilt_s + rotated_z * tilt_c

    camera_factor = CAMERA_DISTANCE / max(0.4, CAMERA_DISTANCE - depth)
    scale = min((view_rows - 5) / 2.9, (cols - 4) / 3.7)
    center_x = cols / 2
    center_y = (view_rows + 1) / 2 + 0.38 * scale
    screen_x = int(center_x + rotated_x * camera_factor * scale * 1.9)
    screen_y = int(center_y - tilted_y * camera_factor * scale)
    return screen_x, screen_y, depth, camera_factor, scale


def render_frame(points, flowers, angle, cols, rows, home_cursor=False):
    view_rows = max(8, rows - 2)
    chars = [[" "] * cols for _ in range(rows)]
    colors = [[0] * cols for _ in range(rows)]
    depth_buffer = [[-1e9] * cols for _ in range(rows)]

    def plot(col, row, depth, character, color):
        if 0 <= col < cols and 1 <= row < view_rows and depth > depth_buffer[row][col]:
            depth_buffer[row][col] = depth
            chars[row][col] = character
            colors[row][col] = color

    for position, normal, palette, tone, two_sided, override in points:
        col, row, depth, _, _ = transform_and_project(position, angle, cols, view_rows)
        nx, ny, nz = normal
        ca, sa = math.cos(angle), math.sin(angle)
        nx, nz = nx * ca - nz * sa, nx * sa + nz * ca
        ny, nz = ny * math.cos(TILT) - nz * math.sin(TILT), ny * math.sin(TILT) + nz * math.cos(TILT)
        brightness = 0.28 + 0.72 * max(0.0, nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) + tone
        if two_sided and nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2] < 0:
            brightness = 0.34 + 0.24 * abs(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) + tone
        brightness = min(0.999, max(0.0, brightness))
        ramp = PETAL_MARKS
        if override == "P":
            char = ramp[int(brightness * len(ramp))]
        else:
            char = override or ramp[int(brightness * len(ramp))]
        color = palette[min(len(palette) - 1, int(brightness * len(palette)))]
        plot(col, row, depth, char, color)

    # Keep the six-petal lily heads face-on while their 3D centers orbit the
    # bouquet. This makes every bloom readable as it comes around to the front.
    for center, palette, seed in flowers:
        flower_x, flower_y, depth, camera_factor, scale = transform_and_project(center, angle, cols, view_rows)
        radius_x = max(2.8, 0.18 * camera_factor * scale * 1.9)
        radius_y = max(1.8, 0.18 * camera_factor * scale)
        phase = seed + angle * 0.22
        for row in range(int(flower_y - radius_y) - 1, int(flower_y + radius_y) + 2):
            dy = (row + 0.5 - flower_y) / radius_y
            for col in range(int(flower_x - radius_x) - 1, int(flower_x + radius_x) + 2):
                dx = (col + 0.5 - flower_x) / radius_x
                distance = math.sqrt(dx * dx + dy * dy)
                if distance > 1.0:
                    continue
                petal_angle = math.atan2(dy, dx) + phase
                reach = 0.24 + 0.76 * abs(math.cos(3 * petal_angle)) ** 0.82
                if distance > reach:
                    continue

                if distance < 0.13:
                    character, color = "@", STAMEN[-1]
                elif distance < 0.22:
                    character, color = "*", STAMEN[1]
                else:
                    brightness = 0.72 - 0.20 * dx - 0.22 * dy + 0.10 * distance
                    if distance > reach - 0.12:
                        brightness -= 0.18
                    brightness = min(0.999, max(0.0, brightness))
                    character = PETAL_MARKS[int(brightness * len(PETAL_MARKS))]
                    if abs(math.sin(3 * petal_angle)) < 0.10 and distance < reach - 0.08:
                        character = "+"
                    color = palette[min(len(palette) - 1, int(brightness * len(palette)))]
                plot(col, row, depth + 0.025 * (1.0 - distance), character, color)

        # Three gold-tipped stamens make the center distinct from a generic star.
        for stamen_index in range(3):
            stamen_angle = phase + stamen_index * math.tau / 3
            for length in (0.20, 0.30, 0.40):
                col = int(flower_x + math.cos(stamen_angle) * radius_x * length)
                row = int(flower_y - math.sin(stamen_angle) * radius_y * length)
                plot(col, row, depth + 0.04, "*" if length == 0.40 else ".", STAMEN[-1] if length == 0.40 else STAMEN[1])

    # Place the sender and recipient as two postcard lines in the upper left.
    sender_color = 218
    for index, character in enumerate(FROM_LINE):
        if 2 + index < cols:
            chars[0][2 + index] = character
            colors[0][2 + index] = sender_color
    recipient_start = 2
    for index, character in enumerate(TO_LINE):
        if recipient_start + index < cols:
            chars[1][recipient_start + index] = character
            colors[1][recipient_start + index] = sender_color

    # The short subject sits beneath the bouquet, centered like a card caption.
    start = max(0, (cols - len(SUBJECT)) // 2)
    for index, character in enumerate(SUBJECT):
        if start + index < cols:
            chars[rows - 1][start + index] = character
            colors[rows - 1][start + index] = 225

    output = []
    for row_index, row_chars in enumerate(chars):
        parts = []
        active_color = -1
        for col, character in enumerate(row_chars):
            color = colors[row_index][col]
            if character != " " and color != active_color:
                parts.append(f"\033[38;5;{color}m")
                active_color = color
            parts.append(character)
        output.append("".join(parts))

    prefix = "\033[H" if home_cursor else ""
    return prefix + "\n".join(output) + "\033[0m"


def animate(one_frame=False):
    if os.name == "nt":
        os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    points, flowers = build_scene()
    if one_frame:
        size = shutil.get_terminal_size((84, 30))
        cols, rows = max(42, size.columns - 1), max(18, size.lines - 1)
        print(render_frame(points, flowers, 0.0, cols, rows))
        return

    sys.stdout.write("\033[?25l\033[2J")
    sys.stdout.flush()
    started = time.perf_counter()
    try:
        while True:
            now = time.perf_counter()
            size = shutil.get_terminal_size((84, 30))
            cols, rows = max(42, size.columns - 1), max(18, size.lines - 1)
            sys.stdout.write(render_frame(points, flowers, (now - started) * SPIN_SPEED, cols, rows, home_cursor=True))
            sys.stdout.flush()
            delay = 1 / FPS - (time.perf_counter() - now)
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Show a rotating 360-degree bouquet of twelve lilies.")
    parser.add_argument("--once", action="store_true", help="print one still frame and exit")
    args = parser.parse_args()
    animate(one_frame=args.once)


if __name__ == "__main__":
    main()
