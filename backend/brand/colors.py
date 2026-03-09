"""Color extraction from logo images using ColorThief."""

import os


def extract_colors_from_logo(logo_path: str) -> dict:
    """Extract dominant colors from an uploaded logo image.

    Returns:
        Dictionary with list of hex color codes.
    """
    if not os.path.exists(logo_path):
        return {"error": f"Logo file not found: {logo_path}", "colors": []}

    try:
        from colorthief import ColorThief

        ct = ColorThief(logo_path)
        dominant = ct.get_color(quality=1)
        palette = ct.get_palette(color_count=5, quality=1)
        hex_colors = [
            f"#{r:02x}{g:02x}{b:02x}" for r, g, b in [dominant] + palette
        ]
        return {"colors": hex_colors}
    except Exception as e:
        return {"error": str(e), "colors": ["#1a1a2e", "#16213e", "#e94560"]}
