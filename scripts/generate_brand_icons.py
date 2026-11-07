import sys
from pathlib import Path

# Ensure root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from PIL import Image

def generate_icons():
    app = QApplication.instance() or QApplication(sys.argv)
    
    svg_path = ROOT / "assets" / "brand" / "ghostline.svg"
    svg_bytes = svg_path.read_bytes()
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    
    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    pil_images = []
    
    out_dir = ROOT / "assets" / "brand"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for s in sizes:
        qimg = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
        qimg.fill(QColor(0, 0, 0, 0))
        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        
        png_path = out_dir / f"ghostline-{s}.png"
        qimg.save(str(png_path), "PNG")
        print(f"Generated {png_path.name}")
        
        # Load in Pillow for ICO generation
        pil_img = Image.open(png_path)
        pil_images.append(pil_img)
        
    # Generate multi-resolution ghostline.ico
    # Standard Windows ICO sizes: 16, 24, 32, 48, 64, 128, 256
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [img for s, img in zip(sizes, pil_images) if (s, s) in ico_sizes]
    
    ico_destinations = [
        ROOT / "ghostline.ico",
        ROOT / "assets" / "brand" / "ghostline.ico",
        ROOT / "dist" / "Ghostline" / "_internal" / "ghostline.ico",
        ROOT / "website" / "favicon.ico",
    ]
    
    for dest in ico_destinations:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Pillow save ICO with multi-size
        ico_images[-1].save(
            str(dest),
            format="ICO",
            sizes=[(img.width, img.height) for img in ico_images]
        )
        print(f"Saved multi-res ICO -> {dest}")
        
    # Also save 32px and 256px png for website/branding
    (ROOT / "website" / "icon.png").write_bytes((out_dir / "ghostline-256.png").read_bytes())
    print("Updated website/icon.png")

if __name__ == "__main__":
    generate_icons()

