"""
ZYROX AI Brand Asset Generator.
Generates static PNGs and genuine seamless looping MP4, WebM, and GIF files
using PIL and FFmpeg.
"""

import os
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

BRAND_DIR = os.path.join(os.path.dirname(__file__), "..", "taikry", "web", "assets", "brand")
os.makedirs(BRAND_DIR, exist_ok=True)

# Colors
BG_COLOR = (6, 11, 9)          # #060B09
SURFACE_COLOR = (11, 21, 17)   # #0B1511
BORDER_COLOR = (32, 55, 44)    # #20372C
PRIMARY_EMERALD = (0, 217, 154) # #00D99A
BRIGHT_EMERALD = (22, 230, 171) # #16E6AB
TEXT_WHITE = (234, 255, 245)   # #EAFFF5
TEXT_MUTED = (135, 169, 154)   # #87A99A


def draw_shield(draw, center_x, center_y, size, fill_color, stroke_color, stroke_width=2):
    """Draws an institutional 6-point beveled hex shield."""
    w = size * 0.88
    h = size
    points = [
        (center_x, center_y - h/2),
        (center_x + w/2, center_y - h*0.28),
        (center_x + w/2, center_y + h*0.28),
        (center_x, center_y + h/2),
        (center_x - w/2, center_y + h*0.28),
        (center_x - w/2, center_y - h*0.28),
    ]
    draw.polygon(points, fill=fill_color, outline=stroke_color, width=stroke_width)
    return points


def draw_z_monogram(draw, center_x, center_y, size, color, width=4, phase=0.0):
    """Draws the geometric Z path with light pulse."""
    w = size * 0.52
    h = size * 0.45
    x1, y1 = center_x - w/2, center_y - h/2
    x2, y2 = center_x + w/2, center_y - h/2
    x3, y3 = center_x - w/2, center_y + h/2
    x4, y4 = center_x + w/2, center_y + h/2

    # Top horizontal
    draw.line([(x1, y1), (x2, y1)], fill=color, width=width)
    # Diagonal
    draw.line([(x2, y1), (x3, y4)], fill=color, width=width)
    # Bottom horizontal
    draw.line([(x3, y4), (x4, y4)], fill=color, width=width)

    # Center quantum core
    pulse = 0.5 + 0.5 * math.sin(phase)
    r = int(3 + 2 * pulse)
    core_color = BRIGHT_EMERALD
    draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r], fill=core_color)


def generate_static_icon():
    """Generates 512x512 high-res square icon."""
    size = 512
    img = Image.new("RGBA", (size, size), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # Rounded outer border
    draw.rounded_rectangle([(8, 8), (size-8, size-8)], radius=110, outline=BORDER_COLOR, width=8)

    # Outer Shield
    cx, cy = size // 2, size // 2
    draw_shield(draw, cx, cy, 340, SURFACE_COLOR, BORDER_COLOR, stroke_width=12)
    # Inner Bevel
    draw_shield(draw, cx, cy, 300, None, (0, 217, 154, 50), stroke_width=4)

    # Z Mark
    draw_z_monogram(draw, cx, cy, 300, PRIMARY_EMERALD, width=28, phase=0.0)

    # Inner core halo
    draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=PRIMARY_EMERALD + (80,))
    draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=BRIGHT_EMERALD)

    out_path = os.path.join(BRAND_DIR, "zyrox-logo-icon.png")
    img.save(out_path, "PNG")
    print(f"Generated {out_path} ({os.path.getsize(out_path)} bytes)")


def generate_static_logo():
    """Generates static rectangular brand logo PNG."""
    w, h = 640, 128
    img = Image.new("RGBA", (w, h), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # Shield Monogram
    cx, cy = 64, 64
    draw_shield(draw, cx, cy, 84, SURFACE_COLOR, BORDER_COLOR, stroke_width=3)
    draw_z_monogram(draw, cx, cy, 76, PRIMARY_EMERALD, width=6, phase=0.0)

    # Wordmark text
    # Since system fonts vary, draw clean geometric letterforms or fallback font
    try:
        font_large = ImageFont.truetype("arialbd.ttf", 44)
        font_sub = ImageFont.truetype("arial.ttf", 15)
        font_badge = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_badge = ImageFont.load_default()

    draw.text((130, 32), "ZYROX", fill=TEXT_WHITE, font=font_large)

    # AI Badge Pill
    draw.rounded_rectangle([(330, 40), (385, 72)], radius=6, fill=SURFACE_COLOR, outline=PRIMARY_EMERALD, width=2)
    draw.text((342, 44), "AI", fill=PRIMARY_EMERALD, font=font_badge)

    # Tagline
    draw.text((132, 86), "READ THE MARKET. OWN YOUR EDGE.", fill=TEXT_MUTED, font=font_sub)

    out_path = os.path.join(BRAND_DIR, "zyrox-logo-static.png")
    img.save(out_path, "PNG")
    print(f"Generated {out_path} ({os.path.getsize(out_path)} bytes)")


def generate_seamless_video_loop():
    """
    Renders 135 frames (4.5 seconds at 30 fps) forming an exact mathematical seamless loop.
    Encodes to MP4, WebM, and GIF via ffmpeg.
    """
    frames_dir = os.path.join(BRAND_DIR, "_tmp_frames")
    os.makedirs(frames_dir, exist_ok=True)

    fps = 30
    duration = 4.5
    total_frames = int(fps * duration)
    w, h = 640, 128

    try:
        font_large = ImageFont.truetype("arialbd.ttf", 44)
        font_sub = ImageFont.truetype("arial.ttf", 15)
        font_badge = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_badge = ImageFont.load_default()

    print(f"Rendering {total_frames} frames for seamless loop...")

    for i in range(total_frames):
        t = i / total_frames  # normalized 0.0 to 1.0
        phase = t * 2 * math.pi  # Exact 2pi periodic boundary!

        img = Image.new("RGBA", (w, h), BG_COLOR + (255,))
        draw = ImageDraw.Draw(img)

        # Subtle breathing scale
        breathe = 0.02 * math.sin(phase)
        size = 84 * (1.0 + breathe)
        cx, cy = 64, 64

        # Shield
        draw_shield(draw, cx, cy, size, SURFACE_COLOR, BORDER_COLOR, stroke_width=3)

        # Dynamic light sweep color
        sweep_val = 0.5 + 0.5 * math.sin(phase)
        r = int(PRIMARY_EMERALD[0] + (BRIGHT_EMERALD[0] - PRIMARY_EMERALD[0]) * sweep_val)
        g = int(PRIMARY_EMERALD[1] + (BRIGHT_EMERALD[1] - PRIMARY_EMERALD[1]) * sweep_val)
        b = int(PRIMARY_EMERALD[2] + (BRIGHT_EMERALD[2] - PRIMARY_EMERALD[2]) * sweep_val)
        current_emerald = (r, g, b)

        # Monogram
        draw_z_monogram(draw, cx, cy, size * 0.9, current_emerald, width=6, phase=phase)

        # Shimmer on text
        shimmer_x = int(120 + 300 * t)
        text_color = TEXT_WHITE
        draw.text((130, 32), "ZYROX", fill=text_color, font=font_large)

        # AI Badge Pill
        draw.rounded_rectangle([(330, 40), (385, 72)], radius=6, fill=SURFACE_COLOR, outline=current_emerald, width=2)
        draw.text((342, 44), "AI", fill=current_emerald, font=font_badge)

        # Tagline
        draw.text((132, 86), "READ THE MARKET. OWN YOUR EDGE.", fill=TEXT_MUTED, font=font_sub)

        frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
        img.save(frame_path, "PNG")

    # Encode with FFmpeg
    # 1. MP4 (H.264, yuv420p for max browser compatibility)
    mp4_out = os.path.join(BRAND_DIR, "zyrox-logo-loop.mp4")
    cmd_mp4 = [
        "ffmpeg", "-y", "-r", str(fps),
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        mp4_out
    ]
    subprocess.run(cmd_mp4, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Generated {mp4_out} ({os.path.getsize(mp4_out)} bytes)")

    # 2. WebM (VP9, high compression, ideal for web)
    webm_out = os.path.join(BRAND_DIR, "zyrox-logo-loop.webm")
    cmd_webm = [
        "ffmpeg", "-y", "-r", str(fps),
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30",
        webm_out
    ]
    subprocess.run(cmd_webm, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Generated {webm_out} ({os.path.getsize(webm_out)} bytes)")

    # 3. GIF (Optimized palette)
    gif_out = os.path.join(BRAND_DIR, "zyrox-logo-loop.gif")
    palette_path = os.path.join(frames_dir, "palette.png")
    cmd_pal = [
        "ffmpeg", "-y", "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-vf", "fps=24,scale=480:-1:flags=lanczos,palettegen",
        palette_path
    ]
    subprocess.run(cmd_pal, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cmd_gif = [
        "ffmpeg", "-y", "-r", "24",
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-i", palette_path,
        "-lavfi", "fps=24,scale=480:-1:flags=lanczos [x]; [x][1:v] paletteuse",
        gif_out
    ]
    subprocess.run(cmd_gif, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Generated {gif_out} ({os.path.getsize(gif_out)} bytes)")

    # Clean up temp frames
    for f in os.listdir(frames_dir):
        try:
            os.remove(os.path.join(frames_dir, f))
        except Exception:
            pass
    try:
        os.rmdir(frames_dir)
    except Exception:
        pass


def generate_hero_video():
    """Generates 1280x720 Hero video animation."""
    frames_dir = os.path.join(BRAND_DIR, "_tmp_hero_frames")
    os.makedirs(frames_dir, exist_ok=True)

    fps = 30
    duration = 5.0
    total_frames = int(fps * duration)
    w, h = 1280, 720

    try:
        font_large = ImageFont.truetype("arialbd.ttf", 76)
        font_sub = ImageFont.truetype("arial.ttf", 24)
        font_badge = ImageFont.truetype("arialbd.ttf", 36)
    except Exception:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_badge = ImageFont.load_default()

    print(f"Rendering {total_frames} frames for hero animation...")

    cx, cy = w // 2, 260
    for i in range(total_frames):
        t = i / total_frames
        phase = t * 2 * math.pi

        img = Image.new("RGBA", (w, h), BG_COLOR + (255,))
        draw = ImageDraw.Draw(img)

        # Radial aura effect
        breathe = 0.03 * math.sin(phase)
        size = 200 * (1.0 + breathe)

        draw_shield(draw, cx, cy, size, SURFACE_COLOR, BORDER_COLOR, stroke_width=6)
        draw_shield(draw, cx, cy, size * 0.88, None, (0, 217, 154, 40), stroke_width=2)

        sweep_val = 0.5 + 0.5 * math.sin(phase)
        r = int(PRIMARY_EMERALD[0] + (BRIGHT_EMERALD[0] - PRIMARY_EMERALD[0]) * sweep_val)
        g = int(PRIMARY_EMERALD[1] + (BRIGHT_EMERALD[1] - PRIMARY_EMERALD[1]) * sweep_val)
        b = int(PRIMARY_EMERALD[2] + (BRIGHT_EMERALD[2] - PRIMARY_EMERALD[2]) * sweep_val)
        current_emerald = (r, g, b)

        draw_z_monogram(draw, cx, cy, size * 0.9, current_emerald, width=16, phase=phase)

        # Wordmark
        draw.text((450, 430), "ZYROX", fill=TEXT_WHITE, font=font_large)

        # AI Badge
        draw.rounded_rectangle([(770, 442), (860, 502)], radius=10, fill=SURFACE_COLOR, outline=current_emerald, width=3)
        draw.text((790, 452), "AI", fill=current_emerald, font=font_badge)

        # Tagline
        tagline = "READ THE MARKET. OWN YOUR EDGE."
        draw.text((410, 540), tagline, fill=TEXT_MUTED, font=font_sub)

        frame_path = os.path.join(frames_dir, f"hero_{i:04d}.png")
        img.save(frame_path, "PNG")

    hero_mp4 = os.path.join(BRAND_DIR, "zyrox-logo-hero.mp4")
    cmd = [
        "ffmpeg", "-y", "-r", str(fps),
        "-i", os.path.join(frames_dir, "hero_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        hero_mp4
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Generated {hero_mp4} ({os.path.getsize(hero_mp4)} bytes)")

    # Clean up
    for f in os.listdir(frames_dir):
        try:
            os.remove(os.path.join(frames_dir, f))
        except Exception:
            pass
    try:
        os.rmdir(frames_dir)
    except Exception:
        pass


if __name__ == "__main__":
    generate_static_icon()
    generate_static_logo()
    generate_seamless_video_loop()
    generate_hero_video()
    print("All ZYROX AI brand assets successfully rendered!")
