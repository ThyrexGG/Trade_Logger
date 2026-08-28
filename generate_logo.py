import os
import math
from PIL import Image, ImageDraw, ImageFilter

def create_trade_logger_icon(size=1024):
    # Base dark canvas with subtle radial depth
    img = Image.new("RGBA", (size, size), (12, 15, 22, 255))
    draw = ImageDraw.Draw(img)
    
    # Outer rounded container with glowing border
    pad = int(size * 0.08)
    radius = int(size * 0.22)
    
    # Glow layer
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    
    # Subtle inner gradient background
    bg_box = [pad, pad, size - pad, size - pad]
    glow_draw.rounded_rectangle(bg_box, radius=radius, fill=(18, 24, 38, 255), outline=(0, 255, 204, 180), width=int(size * 0.015))
    
    # Neon glow backdrop for chart
    center_x, center_y = size // 2, size // 2
    for r in range(int(size * 0.35), 0, -10):
        alpha = int(25 * (1 - r / (size * 0.35)))
        glow_draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=(0, 255, 204, alpha)
        )
        
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)
    
    # Draw Trading Candlesticks
    # Candle 1 (Bullish green, left)
    c1_x = int(size * 0.30)
    c1_w = int(size * 0.08)
    draw.line([(c1_x, int(size * 0.42)), (c1_x, int(size * 0.72))], fill=(0, 255, 204, 255), width=int(size * 0.012))
    draw.rounded_rectangle(
        [c1_x - c1_w//2, int(size * 0.48), c1_x + c1_w//2, int(size * 0.65)],
        radius=int(size*0.015),
        fill=(0, 255, 204, 255)
    )
    
    # Candle 2 (Small pullback, blue-tinted red)
    c2_x = int(size * 0.46)
    c2_w = int(size * 0.08)
    draw.line([(c2_x, int(size * 0.38)), (c2_x, int(size * 0.62))], fill=(0, 150, 255, 255), width=int(size * 0.012))
    draw.rounded_rectangle(
        [c2_x - c2_w//2, int(size * 0.43), c2_x + c2_w//2, int(size * 0.56)],
        radius=int(size*0.015),
        fill=(0, 150, 255, 255)
    )
    
    # Candle 3 (Major breakout green, right)
    c3_x = int(size * 0.62)
    c3_w = int(size * 0.08)
    draw.line([(c3_x, int(size * 0.24)), (c3_x, int(size * 0.58))], fill=(0, 255, 204, 255), width=int(size * 0.012))
    draw.rounded_rectangle(
        [c3_x - c3_w//2, int(size * 0.28), c3_x + c3_w//2, int(size * 0.50)],
        radius=int(size*0.015),
        fill=(0, 255, 204, 255)
    )
    
    # Sleek Trendline with breakout arrow
    trend_points = [
        (int(size * 0.22), int(size * 0.68)),
        (int(size * 0.38), int(size * 0.54)),
        (int(size * 0.52), int(size * 0.58)),
        (int(size * 0.74), int(size * 0.28)),
    ]
    draw.line(trend_points, fill=(255, 255, 255, 240), width=int(size * 0.018), joint="curve")
    
    # Arrowhead at peak
    peak_x, peak_y = trend_points[-1]
    arrow_size = int(size * 0.05)
    arrow_poly = [
        (peak_x, peak_y - arrow_size),
        (peak_x + arrow_size, peak_y + int(arrow_size * 0.3)),
        (peak_x - int(arrow_size * 0.2), peak_y),
    ]
    draw.polygon(arrow_poly, fill=(0, 255, 204, 255))
    
    # Glowing node circles at trend joints
    for pt in trend_points[:-1]:
        draw.ellipse(
            [pt[0] - int(size*0.018), pt[1] - int(size*0.018), pt[0] + int(size*0.018), pt[1] + int(size*0.018)],
            fill=(0, 255, 204, 255),
            outline=(255, 255, 255, 255),
            width=int(size*0.005)
        )
        
    return img

if __name__ == "__main__":
    master_icon = create_trade_logger_icon(1024)
    
    # 1. Save master artifact
    master_icon.save("trade_logger_logo.png", "PNG")
    print("Master 1024x1024 logo created at trade_logger_logo.png")
    
    # 2. Deploy to Android Mipmap densities
    res_base = os.path.join("flutter_app", "android", "app", "src", "main", "res")
    density_map = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    
    for folder, dim in density_map.items():
        folder_path = os.path.join(res_base, folder)
        if os.path.exists(folder_path):
            resized = master_icon.resize((dim, dim), Image.Resampling.LANCZOS)
            target = os.path.join(folder_path, "ic_launcher.png")
            resized.save(target, "PNG")
            print(f"Updated Android icon: {target} ({dim}x{dim})")
            
    # 3. Deploy to Flutter Web & App icons
    web_icons = [
        (os.path.join("flutter_app", "web", "favicon.png"), (32, 32)),
        (os.path.join("flutter_app", "web", "icons", "Icon-192.png"), (192, 192)),
        (os.path.join("flutter_app", "web", "icons", "Icon-512.png"), (512, 512)),
        (os.path.join("flutter_app", "web", "icons", "Icon-maskable-192.png"), (192, 192)),
        (os.path.join("flutter_app", "web", "icons", "Icon-maskable-512.png"), (512, 512)),
    ]
    for path, dims in web_icons:
        if os.path.exists(os.path.dirname(path)):
            master_icon.resize(dims, Image.Resampling.LANCZOS).save(path, "PNG")
            print(f"Updated web/flutter icon: {path} ({dims[0]}x{dims[1]})")

    print("\nAll Android and Flutter icons updated successfully!")
