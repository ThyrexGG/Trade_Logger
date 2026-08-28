import os
from PIL import Image, ImageDraw

densities = {
    "drawable-mdpi": 24,
    "drawable-hdpi": 36,
    "drawable-xhdpi": 48,
    "drawable-xxhdpi": 72,
    "drawable-xxxhdpi": 96,
    "drawable": 48
}

base_res = r"c:\Users\Asus\Desktop\Trade_Logger\flutter_app\android\app\src\main\res"

for folder, size in densities.items():
    dir_path = os.path.join(base_res, folder)
    os.makedirs(dir_path, exist_ok=True)
    
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    scale = size / 24.0
    
    # Candle 1 (left)
    draw.rectangle([5*scale, 5*scale, 7*scale, 15*scale], fill=(255, 255, 255, 255))
    draw.rectangle([5.6*scale, 3*scale, 6.4*scale, 17*scale], fill=(255, 255, 255, 255))
    
    # Candle 2 (middle)
    draw.rectangle([10.5*scale, 3*scale, 12.5*scale, 13*scale], fill=(255, 255, 255, 255))
    draw.rectangle([11.1*scale, 1*scale, 11.9*scale, 15*scale], fill=(255, 255, 255, 255))
    
    # Candle 3 (right)
    draw.rectangle([16*scale, 1*scale, 18*scale, 10*scale], fill=(255, 255, 255, 255))
    draw.rectangle([16.6*scale, 0*scale, 17.4*scale, 12*scale], fill=(255, 255, 255, 255))
    
    # Trend curve / line across bottom
    draw.line([3*scale, 19*scale, 9*scale, 16*scale, 15*scale, 12*scale, 21*scale, 6*scale], fill=(255, 255, 255, 255), width=max(1, int(1.5*scale)))
    
    out_file = os.path.join(dir_path, "ic_notification.png")
    img.save(out_file, "PNG")
    print(f"Saved {out_file} ({size}x{size})")

print("All Android notification bitmap drawables generated successfully!")
