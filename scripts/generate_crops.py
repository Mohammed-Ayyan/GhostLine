import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BEFORE_DIR = ROOT / "reports" / "run6" / "real_shots_before" / "scale_125pct"
AFTER_DIR = ROOT / "reports" / "run6" / "real_shots_after" / "scale_125pct"
CROPS_DIR = ROOT / "reports" / "run6" / "crops"
CROPS_DIR.mkdir(parents=True, exist_ok=True)

def load_img(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")

def create_side_by_side(
    before_img: Image.Image,
    after_img: Image.Image,
    box_before: tuple,
    box_after: tuple,
    title: str,
    out_filename: str
):
    # Crop
    crop_b = before_img.crop(box_before)
    crop_a = after_img.crop(box_after)

    # 2x Zoom
    scale = 2
    w_b, h_b = crop_b.size
    w_a, h_a = crop_a.size
    crop_b_2x = crop_b.resize((w_b * scale, h_b * scale), Image.Resampling.LANCZOS)
    crop_a_2x = crop_a.resize((w_a * scale, h_a * scale), Image.Resampling.LANCZOS)

    header_h = 44
    border = 10
    total_w = crop_b_2x.width + crop_a_2x.width + border * 3
    total_h = max(crop_b_2x.height, crop_a_2x.height) + header_h + border * 2

    canvas = Image.new("RGBA", (total_w, total_h), (26, 26, 26, 255))
    draw = ImageDraw.Draw(canvas)

    # Fonts
    font = None
    for fn in ["segoeui.ttf", "arial.ttf"]:
        try:
            font = ImageFont.truetype(fn, 15)
            font_title = ImageFont.truetype(fn, 16)
            break
        except Exception:
            pass

    # Header Title
    draw.text((border, 12), title, fill=(255, 255, 255, 255), font=font_title)

    # Paste Before
    x_b = border
    y_b = header_h
    draw.text((x_b, header_h - 22), "BEFORE (Old Defect)", fill=(239, 68, 68, 255), font=font)
    canvas.paste(crop_b_2x, (x_b, y_b))
    draw.rectangle([x_b, y_b, x_b + crop_b_2x.width, y_b + crop_b_2x.height], outline=(239, 68, 68, 255), width=2)

    # Paste After
    x_a = x_b + crop_b_2x.width + border
    y_a = header_h
    draw.text((x_a, header_h - 22), "AFTER (Verified Fix)", fill=(34, 197, 94, 255), font=font)
    canvas.paste(crop_a_2x, (x_a, y_a))
    draw.rectangle([x_a, y_a, x_a + crop_a_2x.width, y_a + crop_a_2x.height], outline=(34, 197, 94, 255), width=2)

    out_path = CROPS_DIR / out_filename
    canvas.save(out_path, "PNG")
    print(f"Generated side-by-side crop -> {out_path.name}")

def main():
    b_dash = load_img(BEFORE_DIR / "main_dashboard_1920x1080.png")
    a_dash = load_img(AFTER_DIR / "main_dashboard_1920x1080.png")
    
    b_gen = load_img(BEFORE_DIR / "main_general_1920x1080.png")
    a_gen = load_img(AFTER_DIR / "main_general_1920x1080.png")
    
    b_help = load_img(BEFORE_DIR / "main_help_1920x1080.png")
    a_help = load_img(AFTER_DIR / "main_help_1920x1080.png")

    # D1: Strips behind label (Home screen action card)
    create_side_by_side(
        b_dash, a_dash,
        box_before=(350, 140, 750, 260),
        box_after=(350, 140, 750, 260),
        title="D1: Dark Rectangles (Strips) behind Labels",
        out_filename="D1_strips_comparison.png"
    )

    # D2: Page Subtitles clipped at top (Help & Settings)
    create_side_by_side(
        b_help, a_help,
        box_before=(350, 40, 950, 120),
        box_after=(350, 40, 950, 120),
        title="D2: Page Subtitle Top Line Clipping (Help)",
        out_filename="D2_subtitle_clipping.png"
    )

    # D3: Content Column Width (min(w-64, 960))
    create_side_by_side(
        b_dash, a_dash,
        box_before=(300, 100, 1500, 400),
        box_after=(300, 100, 1500, 400),
        title="D3: Inconsistent / Narrow Column Width vs 960px",
        out_filename="D3_column_width.png"
    )

    # D4: Ampersand mnemonic loss
    create_side_by_side(
        b_gen, a_gen,
        box_before=(350, 360, 750, 440),
        box_after=(350, 320, 750, 400),
        title="D4: Ampersand Mnemonic Marker Loss ('Configure AI Models && Providers')",
        out_filename="D4_mnemonic_loss.png"
    )

    # D5: Button Icon Spacing & Semantic Icons
    create_side_by_side(
        b_dash, a_dash,
        box_before=(750, 30, 1250, 100),
        box_after=(750, 30, 1250, 100),
        title="D5: Button Icon Spacing (8px gap) & Semantic Icons",
        out_filename="D5_icon_spacing.png"
    )

    # D6: Clipped Help Keycap ("Alt + 1 / 2 / 3 / 4")
    create_side_by_side(
        b_help, a_help,
        box_before=(350, 650, 650, 740),
        box_after=(350, 520, 650, 610),
        title="D6: Clipped Help Keycap ('Alt + 1 / 2 / 3 / 4')",
        out_filename="D6_keycap_clipping.png"
    )

    # D7: Combobox Chevron & Icon Preset Row
    create_side_by_side(
        b_gen, a_gen,
        box_before=(800, 680, 1300, 780),
        box_after=(800, 660, 1300, 760),
        title="D7: Combobox Drop-down Chevron & Preset Row Buttons",
        out_filename="D7_combobox_chevron.png"
    )

    # D8: Meaningless Progress Bar in Inference Engine
    create_side_by_side(
        b_gen, a_gen,
        box_before=(350, 200, 950, 320),
        box_after=(350, 200, 950, 300),
        title="D8: Meaningless Blue Progress Bar Removed",
        out_filename="D8_progressbar_removed.png"
    )

    # D9: Fake Seeded Recent Result
    create_side_by_side(
        b_dash, a_dash,
        box_before=(350, 480, 1200, 780),
        box_after=(350, 440, 1200, 720),
        title="D9: Seeded Fake Recent Result replaced with Honest Empty State",
        out_filename="D9_honest_empty_state.png"
    )

    # D10: Brand Asset (Sidebar Icon)
    create_side_by_side(
        b_dash, a_dash,
        box_before=(10, 20, 240, 80),
        box_after=(10, 20, 240, 80),
        title="D10: Brand Asset Mismatch ('R' vs Official Ghost Mark)",
        out_filename="D10_brand_asset.png"
    )

    # D11: Section Heading Alignment
    create_side_by_side(
        b_gen, a_gen,
        box_before=(340, 80, 600, 160),
        box_after=(340, 80, 600, 160),
        title="D11: Section Heading Flush Left Alignment (0px offset)",
        out_filename="D11_heading_alignment.png"
    )

    # D12: Taskbar Button Visibility Setting
    create_side_by_side(
        b_gen, a_gen,
        box_before=(350, 750, 1050, 840),
        box_after=(350, 730, 1050, 820),
        title="D12: Truthful Taskbar Setting Explanation",
        out_filename="D12_taskbar_visibility.png"
    )

    # D13: Unverifiable Claims Sanitization
    create_side_by_side(
        b_gen, a_gen,
        box_before=(350, 220, 1150, 290),
        box_after=(350, 220, 1150, 290),
        title="D13: Unverifiable Superlative Claims Sanitized",
        out_filename="D13_copy_sanitization.png"
    )

    # D14: Help Cheatsheet Rows Uniformity
    create_side_by_side(
        b_help, a_help,
        box_before=(350, 360, 1150, 620),
        box_after=(350, 300, 1150, 560),
        title="D14: Help Cheatsheet Row Height & Grid Uniformity",
        out_filename="D14_cheatsheet_uniformity.png"
    )

if __name__ == "__main__":
    main()
