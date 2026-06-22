"""Build compact GitHub-friendly GIF demos from captured OrbitOps screenshots."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "docs" / "assets" / "screenshots"
DEMOS = ROOT / "docs" / "assets" / "demos"
DEMOS.mkdir(parents=True, exist_ok=True)


def font(size: int):
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def frame(name: str, label: str, size: tuple[int, int]) -> Image.Image:
    source = Image.open(SCREENSHOTS / name).convert("RGB")
    target_w, target_h = size
    scale = max(target_w / source.width, target_h / source.height)
    resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    canvas = resized.crop((left, top, left + target_w, top + target_h))
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((24, 22, 318, 72), radius=16, fill=(5, 12, 22, 225), outline=(59, 130, 246, 180), width=2)
    draw.ellipse((42, 38, 56, 52), fill=(96, 165, 250, 255))
    draw.text((70, 34), label, font=font(21), fill=(248, 250, 252, 255))
    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def build(output: str, items: list[tuple[str, str]], size: tuple[int, int], duration: int):
    frames = [frame(name, label, size) for name, label in items]
    frames[0].save(
        DEMOS / output,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
        disposal=2,
    )


build(
    "product-tour.gif",
    [
        ("dashboard.png", "01 · Operations overview"),
        ("leads.png", "02 · Lead intelligence"),
        ("workflows.png", "03 · LangGraph workflows"),
        ("ai-operations.png", "04 · AI operations"),
    ],
    (960, 600),
    1500,
)

build(
    "approval-flow.gif",
    [
        ("leads.png", "01 · Qualified lead"),
        ("workflows.png", "02 · Agents complete"),
        ("approvals.png", "03 · Human review gate"),
        ("reports.png", "04 · Approved report"),
    ],
    (960, 600),
    1500,
)

build(
    "mobile-experience.gif",
    [
        ("mobile-dashboard.png", "Mobile dashboard"),
        ("mobile-leads.png", "Responsive lead cards"),
        ("mobile-navigation.png", "Touch navigation"),
    ],
    (390, 844),
    1400,
)

print(f"Created portfolio GIFs in {DEMOS}")
