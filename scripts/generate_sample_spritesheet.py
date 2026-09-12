"""Generate default bundled pet assets with Codex-compatible grid specifications."""

import json
import math
import os
from pathlib import Path
import struct
import zlib

CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 9
TOTAL_WIDTH = CELL_WIDTH * COLUMNS  # 1536
TOTAL_HEIGHT = CELL_HEIGHT * ROWS  # 1872


def create_png(width: int, height: int, rgba_bytes: bytes) -> bytes:
    """Encode raw RGBA buffer into a valid PNG file."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    scanlines = bytearray()
    row_bytes = width * 4
    for y in range(height):
        scanlines.append(0)  # Filter type None
        scanlines.extend(rgba_bytes[y * row_bytes : (y + 1) * row_bytes])

    idat = chunk(b"IDAT", zlib.compress(bytes(scanlines), level=6))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def draw_circle(
    buf: bytearray,
    w: int,
    cx: int,
    cy: int,
    radius: int,
    r: int,
    g: int,
    b: int,
    a: int,
) -> None:
    """Draw filled circle onto RGBA bytearray."""
    r_sq = radius * radius
    for dy in range(-radius, radius + 1):
        y = cy + dy
        for dx in range(-radius, radius + 1):
            x = cx + dx
            if dx * dx + dy * dy <= r_sq:
                idx = (y * w + x) * 4
                if 0 <= idx < len(buf) - 3:
                    buf[idx] = r
                    buf[idx + 1] = g
                    buf[idx + 2] = b
                    buf[idx + 3] = a


def draw_rect(
    buf: bytearray,
    w: int,
    x0: int,
    y0: int,
    rw: int,
    rh: int,
    r: int,
    g: int,
    b: int,
    a: int,
) -> None:
    """Draw filled rectangle onto RGBA bytearray."""
    for y in range(y0, y0 + rh):
        for x in range(x0, x0 + rw):
            idx = (y * w + x) * 4
            if 0 <= idx < len(buf) - 3:
                buf[idx] = r
                buf[idx + 1] = g
                buf[idx + 2] = b
                buf[idx + 3] = a


def generate_spritesheet() -> bytes:
    """Render 8x9 spritesheet into raw RGBA and encode as PNG."""
    buf = bytearray(TOTAL_WIDTH * TOTAL_HEIGHT * 4)

    # State theme colors (R, G, B)
    row_colors = [
        (56, 189, 248),  # Row 0: Idle (Sky Blue)
        (74, 222, 128),  # Row 1: Move Left (Green)
        (74, 222, 128),  # Row 2: Move Right (Green)
        (250, 204, 21),  # Row 3: Jump (Yellow / Gold)
        (244, 114, 182),  # Row 4: Wave (Pink)
        (239, 68, 68),  # Row 5: Failed (Red)
        (251, 146, 60),  # Row 6: Waiting (Orange)
        (168, 85, 247),  # Row 7: Working (Purple)
        (45, 212, 191),  # Row 8: Review (Teal)
    ]

    for row in range(ROWS):
        base_color = row_colors[row]
        for col in range(COLUMNS):
            cell_x = col * CELL_WIDTH
            cell_y = row * CELL_HEIGHT

            # Center of the pet in cell
            center_x = cell_x + CELL_WIDTH // 2
            center_y = cell_y + CELL_HEIGHT // 2 + 10

            # Vertical bob or offset per frame
            phase = (col / COLUMNS) * 2 * math.pi
            bob_y = int(math.sin(phase) * 6)

            if row == 3:  # Jump
                bob_y = -int(math.sin((col / COLUMNS) * math.pi) * 25)
            elif row == 5:  # Failed (shake)
                bob_y = (col % 2) * 4

            py = center_y + bob_y

            # 1. Shadow beneath pet
            shadow_w = 48 - (bob_y if bob_y < 0 else 0)
            shadow_h = 12
            draw_rect(
                buf,
                TOTAL_WIDTH,
                center_x - shadow_w // 2,
                cell_y + CELL_HEIGHT - 28,
                shadow_w,
                shadow_h,
                0,
                0,
                0,
                50,
            )

            # 2. Main Pet Body (Soft round capsule)
            body_radius = 42
            draw_circle(
                buf,
                TOTAL_WIDTH,
                center_x,
                py,
                body_radius,
                base_color[0],
                base_color[1],
                base_color[2],
                255,
            )
            # Body highlight
            draw_circle(
                buf,
                TOTAL_WIDTH,
                center_x - 12,
                py - 12,
                14,
                min(255, base_color[0] + 40),
                min(255, base_color[1] + 40),
                min(255, base_color[2] + 40),
                255,
            )

            # 3. Ears
            ear_offset_x = 24
            ear_y = py - 38
            draw_circle(
                buf,
                TOTAL_WIDTH,
                center_x - ear_offset_x,
                ear_y,
                12,
                base_color[0],
                base_color[1],
                base_color[2],
                255,
            )
            draw_circle(
                buf,
                TOTAL_WIDTH,
                center_x + ear_offset_x,
                ear_y,
                12,
                base_color[0],
                base_color[1],
                base_color[2],
                255,
            )

            # 4. Eyes & Expressions per state
            eye_y = py - 6
            if row == 5:  # Failed: 'X' eyes
                # Left X
                draw_rect(buf, TOTAL_WIDTH, center_x - 20, eye_y - 4, 8, 8, 30, 30, 30, 255)
                draw_rect(buf, TOTAL_WIDTH, center_x + 12, eye_y - 4, 8, 8, 30, 30, 30, 255)
                # Tear / sweat drop
                draw_circle(buf, TOTAL_WIDTH, center_x + 28, eye_y + 4, 6, 96, 165, 250, 240)
            elif row == 6:  # Waiting: looking sideways
                eye_dx = int(math.sin(phase) * 4)
                draw_circle(buf, TOTAL_WIDTH, center_x - 16 + eye_dx, eye_y, 6, 30, 30, 30, 255)
                draw_circle(buf, TOTAL_WIDTH, center_x + 16 + eye_dx, eye_y, 6, 30, 30, 30, 255)
            elif row == 7:  # Working: focused visor + computer glow
                # Screen glow
                draw_rect(buf, TOTAL_WIDTH, center_x - 28, py + 12, 56, 18, 59, 130, 246, 230)
                draw_circle(buf, TOTAL_WIDTH, center_x - 14, eye_y, 6, 255, 255, 255, 255)
                draw_circle(buf, TOTAL_WIDTH, center_x + 14, eye_y, 6, 255, 255, 255, 255)
            elif row == 4:  # Wave: waving paw
                paw_y = py - 20 + int(math.sin(phase * 2) * 12)
                draw_circle(
                    buf,
                    TOTAL_WIDTH,
                    center_x + 36,
                    paw_y,
                    10,
                    base_color[0],
                    base_color[1],
                    base_color[2],
                    255,
                )
                draw_circle(buf, TOTAL_WIDTH, center_x - 14, eye_y, 6, 30, 30, 30, 255)
                draw_circle(buf, TOTAL_WIDTH, center_x + 14, eye_y, 6, 30, 30, 30, 255)
            else:  # Normal eyes with blinking on frame 4
                is_blink = col == 4
                if is_blink:
                    draw_rect(buf, TOTAL_WIDTH, center_x - 20, eye_y, 10, 3, 30, 30, 30, 255)
                    draw_rect(buf, TOTAL_WIDTH, center_x + 10, eye_y, 10, 3, 30, 30, 30, 255)
                else:
                    draw_circle(buf, TOTAL_WIDTH, center_x - 16, eye_y, 6, 30, 30, 30, 255)
                    draw_circle(buf, TOTAL_WIDTH, center_x + 16, eye_y, 6, 30, 30, 30, 255)
                    # Eye shine
                    draw_circle(buf, TOTAL_WIDTH, center_x - 18, eye_y - 2, 2, 255, 255, 255, 255)
                    draw_circle(buf, TOTAL_WIDTH, center_x + 14, eye_y - 2, 2, 255, 255, 255, 255)

            # 5. Row specific accessory/prop
            if row == 8:  # Review: magnifying glass
                draw_circle(buf, TOTAL_WIDTH, center_x + 28, py + 8, 12, 148, 163, 184, 255)
                draw_circle(buf, TOTAL_WIDTH, center_x + 28, py + 8, 8, 226, 232, 240, 200)
                draw_rect(buf, TOTAL_WIDTH, center_x + 36, py + 16, 8, 12, 100, 116, 139, 255)
            elif row == 3:  # Jump: sparkle stars
                sparkle_y = py - 40 - abs(bob_y)
                draw_rect(buf, TOTAL_WIDTH, center_x + 30, sparkle_y, 6, 6, 254, 240, 138, 240)
                draw_rect(buf, TOTAL_WIDTH, center_x - 32, sparkle_y + 10, 5, 5, 254, 240, 138, 240)

    return create_png(TOTAL_WIDTH, TOTAL_HEIGHT, bytes(buf))


def main() -> None:
    output_dir = Path(__file__).resolve().parent.parent / "assets" / "pets" / "default"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write pet.json metadata
    pet_meta = {
        "id": "default",
        "name": "Antigravity Pet",
        "version": "1.0.0",
        "author": "Antigravity",
        "grid": {
            "columns": COLUMNS,
            "rows": ROWS,
            "cell_width": CELL_WIDTH,
            "cell_height": CELL_HEIGHT,
        },
        "fps": 10,
        "animations": {
            "idle": {"row": 0, "frames": 8, "fps": 8},
            "move_left": {"row": 1, "frames": 8, "fps": 12},
            "move_right": {"row": 2, "frames": 8, "fps": 12},
            "jump": {"row": 3, "frames": 8, "fps": 10},
            "wave": {"row": 4, "frames": 8, "fps": 8},
            "failed": {"row": 5, "frames": 8, "fps": 8},
            "waiting": {"row": 6, "frames": 8, "fps": 6},
            "working": {"row": 7, "frames": 8, "fps": 12},
            "review": {"row": 8, "frames": 8, "fps": 8},
        },
    }

    pet_json_path = output_dir / "pet.json"
    with open(pet_json_path, "w", encoding="utf-8") as f:
        json.dump(pet_meta, f, indent=2)
    print(f"Wrote {pet_json_path}")

    # 2. Write spritesheet.png
    png_data = generate_spritesheet()
    spritesheet_path = output_dir / "spritesheet.png"
    with open(spritesheet_path, "wb") as f:
        f.write(png_data)
    print(f"Wrote {spritesheet_path} ({len(png_data)} bytes)")


if __name__ == "__main__":
    main()
