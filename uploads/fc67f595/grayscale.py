import base64
import struct
import zlib

# -------------------------------------------------------
# This script creates a small color image from scratch,
# converts it to grayscale using pure Python (no libraries),
# then saves both as PNG files and prints the results.
# No Pillow or external packages needed.
# -------------------------------------------------------

def make_png(width, height, pixels, mode="RGB"):
    """
    Build a PNG file in memory from a list of pixel values.
    pixels = list of (R, G, B) tuples for RGB, or int values for grayscale.
    """
    def png_chunk(chunk_type, data):
        # Each PNG chunk = length + type + data + CRC checksum
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    # PNG file signature (every PNG starts with this)
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk: image width, height, bit depth, color type
    color_type = 2 if mode == "RGB" else 0  # 2 = RGB, 0 = Grayscale
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)

    # IDAT chunk: the actual pixel data, compressed
    raw_rows = []
    for y in range(height):
        row = b'\x00'  # filter type 0 (no filter) for each row
        for x in range(width):
            px = pixels[y * width + x]
            if mode == "RGB":
                row += bytes(px)       # (R, G, B)
            else:
                row += bytes([px])     # single grayscale value
        raw_rows.append(row)

    raw_data = b''.join(raw_rows)
    compressed = zlib.compress(raw_data)
    idat = png_chunk(b'IDAT', compressed)

    # IEND chunk: marks the end of the PNG file
    iend = png_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


def to_grayscale(rgb_pixels):
    """
    Convert a list of (R, G, B) pixels to grayscale.
    Uses the standard luminance formula: 0.299R + 0.587G + 0.114B
    This matches how human eyes perceive brightness.
    """
    gray_pixels = []
    for (r, g, b) in rgb_pixels:
        gray = int(0.299 * r + 0.587 * g + 0.114 * b)
        gray_pixels.append(gray)
    return gray_pixels


# --- Create a simple 8x8 color test image ---
# Each pixel is an (R, G, B) tuple
width, height = 8, 8
color_pixels = []

for y in range(height):
    for x in range(width):
        r = int((x / width) * 255)        # red increases left to right
        g = int((y / height) * 255)       # green increases top to bottom
        b = 128                            # blue is constant
        color_pixels.append((r, g, b))

# --- Convert to grayscale ---
gray_pixels = to_grayscale(color_pixels)

# --- Save color PNG ---
color_png = make_png(width, height, color_pixels, mode="RGB")
with open("/tmp/color.png", "wb") as f:
    f.write(color_png)

# --- Save grayscale PNG ---
gray_png = make_png(width, height, gray_pixels, mode="L")
with open("/tmp/grayscale.png", "wb") as f:
    f.write(gray_png)

# --- Print results ---
print(f"Image size: {width}x{height} pixels")
print(f"Total pixels processed: {len(color_pixels)}")
print()
print("Sample color pixels (R, G, B):")
for i, px in enumerate(color_pixels[:5]):
    print(f"  Pixel {i}: RGB{px}")

print()
print("Sample grayscale values:")
for i, val in enumerate(gray_pixels[:5]):
    print(f"  Pixel {i}: Gray = {val}")

print()
print("Color image saved to:     /tmp/color.png")
print("Grayscale image saved to: /tmp/grayscale.png")
print("Grayscale conversion complete!")
