import os
import struct
import zlib
import base64

# -------------------------------------------------------
# Grayscale converter — reads a real image from /input/
# If no image is provided, generates a test gradient.
# Outputs the grayscale image as base64 so the UI can
# display it directly in the browser.
# -------------------------------------------------------

def read_png(path):
    """Read a PNG file and return (width, height, list of (R,G,B) pixels)."""
    with open(path, "rb") as f:
        data = f.read()

    # Skip the 8-byte PNG signature
    pos = 8
    width = height = 0
    idat_data = b""

    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        pos += 12 + length

        if chunk_type == b"IHDR":
            width = struct.unpack(">I", chunk_data[0:4])[0]
            height = struct.unpack(">I", chunk_data[4:8])[0]
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
            if bit_depth != 8 or color_type not in (2, 6):
                raise ValueError("Only 8-bit RGB or RGBA PNG supported.")
        elif chunk_type == b"IDAT":
            idat_data += chunk_data

    raw = zlib.decompress(idat_data)
    channels = 4 if color_type == 6 else 3
    pixels = []
    stride = width * channels + 1  # +1 for filter byte per row

    for y in range(height):
        row_start = y * stride + 1  # skip filter byte
        for x in range(width):
            offset = row_start + x * channels
            r = raw[offset]
            g = raw[offset + 1]
            b = raw[offset + 2]
            pixels.append((r, g, b))

    return width, height, pixels


def make_png(width, height, pixels, mode="RGB"):
    """Build a PNG file in memory from pixel data."""
    def png_chunk(chunk_type, data):
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b'\x89PNG\r\n\x1a\n'
    color_type = 2 if mode == "RGB" else 0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)

    raw_rows = []
    for y in range(height):
        row = b'\x00'
        for x in range(width):
            px = pixels[y * width + x]
            row += bytes(px) if mode == "RGB" else bytes([px])
        raw_rows.append(row)

    compressed = zlib.compress(b''.join(raw_rows))
    idat = png_chunk(b'IDAT', compressed)
    iend = png_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


def to_grayscale(rgb_pixels):
    """Convert RGB pixels to grayscale using luminance formula."""
    return [int(0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in rgb_pixels]


# --- Find input image in /input/ ---
input_dir = "/input"
input_image_path = None

if os.path.exists(input_dir):
    for fname in os.listdir(input_dir):
        if fname.lower().endswith((".png", ".jpg", ".jpeg")):
            input_image_path = os.path.join(input_dir, fname)
            break

# --- Load or generate image ---
if input_image_path:
    print(f"Reading image: {os.path.basename(input_image_path)}")
    try:
        width, height, color_pixels = read_png(input_image_path)
        print(f"Image size: {width}x{height} pixels")
    except Exception as e:
        print(f"Could not read image: {e}")
        print("Falling back to generated test image.")
        input_image_path = None

if not input_image_path:
    # Generate a simple 64x64 color gradient as fallback
    width, height = 64, 64
    color_pixels = []
    for y in range(height):
        for x in range(width):
            r = int((x / width) * 255)
            g = int((y / height) * 255)
            b = 128
            color_pixels.append((r, g, b))
    print(f"Generated test image: {width}x{height} pixels")

# --- Convert to grayscale ---
gray_pixels = to_grayscale(color_pixels)

# --- Build grayscale PNG in memory ---
gray_png_bytes = make_png(width, height, gray_pixels, mode="L")

# --- Encode as base64 and print for the UI to display ---
b64 = base64.b64encode(gray_png_bytes).decode("utf-8")

print(f"Total pixels processed: {width * height}")
print()
print("Sample original pixels (R, G, B):")
for i, px in enumerate(color_pixels[:5]):
    print(f"  Pixel {i}: RGB{px}")

print()
print("Sample grayscale values:")
for i, val in enumerate(gray_pixels[:5]):
    print(f"  Pixel {i}: Gray = {val}")

print()
print("Grayscale conversion complete!")
print(f"IMAGE_OUTPUT_BASE64:{b64}")
