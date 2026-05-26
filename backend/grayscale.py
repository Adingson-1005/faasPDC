from PIL import Image
import os
import base64
import io

# -------------------------------------------------------
# Grayscale converter using Pillow (auto-installed).
# Reads a real image from /input/ if provided,
# otherwise generates a test gradient.
# Outputs the grayscale image as base64 for the UI.
# -------------------------------------------------------

input_dir = "/input"
input_image_path = None

# Look for an image file in /input/
if os.path.exists(input_dir):
    for fname in os.listdir(input_dir):
        if fname.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
            input_image_path = os.path.join(input_dir, fname)
            break

if input_image_path:
    print(f"Reading image: {os.path.basename(input_image_path)}")
    img = Image.open(input_image_path).convert("RGB")
    print(f"Image size: {img.width}x{img.height} pixels")
    print(f"Mode: {img.mode}")
else:
    # Generate a simple 128x128 color gradient as fallback
    print("No input image found. Generating test gradient...")
    img = Image.new("RGB", (128, 128))
    pixels = img.load()
    for y in range(128):
        for x in range(128):
            pixels[x, y] = (int(x * 2), int(y * 2), 128)
    print(f"Generated test image: {img.width}x{img.height} pixels")

# Convert to grayscale using Pillow
gray_img = img.convert("L")

# Sample some pixel values before and after
print(f"\nTotal pixels: {img.width * img.height}")
print("\nSample pixels (original → grayscale):")
for i, (x, y) in enumerate([(0,0),(10,10),(20,20),(30,30),(40,40)]):
    if x < img.width and y < img.height:
        orig = img.getpixel((x, y))
        gray = gray_img.getpixel((x, y))
        print(f"  ({x},{y}): RGB{orig} → Gray={gray}")

# Encode grayscale image as base64 PNG for the UI to display
buffer = io.BytesIO()
gray_img.save(buffer, format="PNG")
b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

print("\nGrayscale conversion complete!")
print(f"IMAGE_OUTPUT_BASE64:{b64}")
