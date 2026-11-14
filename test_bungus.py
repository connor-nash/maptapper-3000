"""
Local preview script for the Bungus Jones wanted poster.

Usage:
    python test_bungus.py

Output: bungus_test_output.png  — open this to review the layout.

Tip: drop any image file named test_avatar.png into this directory to use
     a real avatar instead of the colored placeholder.
"""

import io
import os
from PIL import Image

OUTPUT_PATH = "bungus_test_output.png"
TEST_USERNAME = "Scrub McGee"
TEST_SCORE = 120


def _make_placeholder_avatar() -> bytes:
    img = Image.new("RGBA", (256, 256), color=(100, 149, 237, 255))  # cornflower blue
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


if __name__ == "__main__":
    if not os.path.exists("wanted_template.png"):
        print("ERROR: wanted_template.png not found in this directory.")
        print("       Put your blank wanted-poster background there and try again.")
        raise SystemExit(1)

    if os.path.exists("test_avatar.png"):
        with open("test_avatar.png", "rb") as f:
            avatar_bytes = f.read()
        print("Using test_avatar.png as the avatar.")
    else:
        avatar_bytes = _make_placeholder_avatar()
        print("No test_avatar.png found — using a blue placeholder.")
        print("Drop any PNG/JPG named test_avatar.png here to test with a real face.")

    from bungus import generate_wanted_poster
    buf = generate_wanted_poster(avatar_bytes, TEST_USERNAME, TEST_SCORE)

    with open(OUTPUT_PATH, "wb") as f:
        f.write(buf.read())

    print(f"\nSaved: {OUTPUT_PATH}")
    print("Open that file and adjust the constants at the top of bungus.py until it looks right.")
