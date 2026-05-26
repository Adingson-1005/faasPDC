from PIL import Image
import sys
import os

def convert_to_grayscale(input_path, output_path=None):
    # Open image
    img = Image.open(input_path)

    # Convert to grayscale
    gray_img = img.convert("L")

    # If no output path is given, auto-generate one
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_grayscale{ext}"

    # Save result
    gray_img.save(output_path)

    print(f"Grayscale image saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python grayscale.py <input_image> [output_image]")
    else:
        input_image = sys.argv[1]
        output_image = sys.argv[2] if len(sys.argv) > 2 else None
        convert_to_grayscale(input_image, output_image)