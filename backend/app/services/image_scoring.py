from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from PIL import Image, ImageFilter


@dataclass
class ScoreResult:
    score: float
    reason: str
    white_ratio: float
    edge_density: float
    background_score: float
    spec_sheet: bool
    aspect_ratio: float
    width: int
    height: int

    def to_dict(self) -> dict:
        return asdict(self)


def _heuristic_score(image_path: Path) -> ScoreResult:
    """
    Lightweight heuristic scoring:
      - downscale aggressively to limit compute
      - estimate "white background ratio" via sampling
      - estimate edge density via FIND_EDGES on a downscaled grayscale
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            orig_w, orig_h = img.size
            if orig_w == 0 or orig_h == 0:
                return ScoreResult(0.0, "invalid image size", 0.0, 0.0, 0.0, False, 0.0, orig_w, orig_h)

            # Für Performance verkleinern, Seitenverhältnis bleibt erhalten.
            img.thumbnail((512, 512))

            w, h = img.size
            if w == 0 or h == 0:
                return ScoreResult(0.0, "invalid image size", 0.0, 0.0, 0.0, False, 0.0, orig_w, orig_h)

            px = img.load()

            # Bis zu ~60k Pixel gleichmäßig sampeln.
            target_samples = min(60000, w * h)
            step = int(((w * h) / target_samples) ** 0.5) or 1

            white = 0
            total = 0
            # Einfacher Schwellwert für weiße Flächen.
            for y in range(0, h, step):
                for x in range(0, w, step):
                    r, g, b = px[x, y]
                    if r > 240 and g > 240 and b > 240:
                        white += 1
                    total += 1
            white_ratio = white / max(total, 1)

            # Kantendichte über Graustufe und FIND_EDGES bestimmen.
            gray = img.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            ep = edges.load()

            edge_hits = 0
            edge_total = 0
            for y in range(0, h, step):
                for x in range(0, w, step):
                    if ep[x, y] > 40:
                        edge_hits += 1
                    edge_total += 1
            edge_density = edge_hits / max(edge_total, 1)

            background_score = max(0.0, min(1.0, (white_ratio - 0.2) / 0.6))
            edge_score = max(0.0, min(1.0, (edge_density - 0.015) / 0.25))

            spec_sheet = white_ratio > 0.7 and edge_density > 0.28
            aspect_ratio = orig_w / orig_h if orig_h else 0.0

            score = 0.6 * background_score + 0.4 * edge_score
            if spec_sheet:
                score *= 0.3

            reason = (
                f"white_ratio={white_ratio:.3f}, edge_density={edge_density:.3f}, "
                f"background={background_score:.3f}, spec_sheet={spec_sheet}"
            )
            return ScoreResult(
                float(score),
                reason,
                white_ratio=float(white_ratio),
                edge_density=float(edge_density),
                background_score=float(background_score),
                spec_sheet=spec_sheet,
                aspect_ratio=float(aspect_ratio),
                width=int(orig_w),
                height=int(orig_h),
            )
    except Exception as e:
        return ScoreResult(0.0, f"error: {e}", 0.0, 0.0, 0.0, False, 0.0, 0, 0)


def score_image(
    image_path: Path,
    vision_model: Optional[str] = None,
) -> ScoreResult:
    """
    If a vision_model is configured, caller may provide a higher-level score elsewhere.
    Fallback to heuristic score here.
    """
    # Im MVP wird hier nur die Heuristik verwendet.
    return _heuristic_score(image_path)