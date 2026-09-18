"""
vision.py
---------
Offline license-plate reading for GateSecAI.

Pipeline for each captured photo:
  1. Save the raw photo to disk (visual record — always kept, even if
     OCR fails or misreads).
  2. Try to find a plate-like rectangular region in the image using
     OpenCV (edge detection + contour shape analysis). This narrows
     what the OCR model has to read, which improves accuracy.
  3. Run EasyOCR (restricted to A-Z and 0-9) on the detected region.
     If no plate-like region was found, fall back to running OCR on
     the whole image instead of giving up.
  4. Return the best-guess plate text + a confidence score. The guard
     always gets a chance to review/correct this before it's saved —
     OCR is a shortcut, not a silent authority.

EasyOCR downloads its recognition model (~65MB) the FIRST time it's
ever used on this machine. That one download needs internet. Every
run after that is 100% offline.
"""

import os
import re
import uuid
from datetime import datetime

import cv2
import numpy as np
import easyocr

# Where captured photos are stored on disk (served statically by main.py).
CAPTURES_DIR = os.path.join(os.path.dirname(__file__), "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        print("[GATEMAN] Loading OCR model (first run downloads it once, needs internet that one time)...")
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        print("[GATEMAN] OCR model ready.")
    return _reader


def save_photo(image_bytes: bytes) -> str:
    """Saves the raw captured photo to disk and returns its filename
    (not full path) so it can be referenced from the database and
    served back via /captures/<filename>."""
    filename = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.jpg"
    filepath = os.path.join(CAPTURES_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filename


def _find_plate_region(image: np.ndarray):
    """Looks for a plate-shaped rectangle in the image using classic
    OpenCV contour detection (no deep learning needed — keeps this
    fully offline and fast). Returns a cropped region, or None if
    nothing plate-shaped was found confidently."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)  # smooths noise, keeps edges
    edges = cv2.Canny(gray, 30, 200)

    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.018 * perimeter, True)

        # A plate looks like a 4-sided shape, roughly rectangular,
        # with a width-to-height ratio typical of real plates.
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h) if h else 0
            if 2.0 <= aspect_ratio <= 6.0 and w > 60 and h > 15:
                return image[y:y + h, x:x + w]

    return None  # nothing confidently plate-shaped — caller will use the full image


def read_plate_from_bytes(image_bytes: bytes):
    """Main entry point. Takes raw uploaded photo bytes, returns:
        (plate_text: str, confidence: float, photo_filename: str)

    plate_text may be an empty string if OCR found nothing readable —
    the caller should treat that as "let the guard type it manually",
    not as an error.
    """
    photo_filename = save_photo(image_bytes)

    np_arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if image is None:
        return "", 0.0, photo_filename

    plate_region = _find_plate_region(image)
    target = plate_region if plate_region is not None else image

    reader = _get_reader()
    results = reader.readtext(
        target,
        allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    )

    if not results:
        return "", 0.0, photo_filename

    # Pick the highest-confidence text block, on the assumption it's
    # most likely to be the plate rather than stray background text.
    best = max(results, key=lambda r: r[2])
    raw_text = best[1]
    confidence = float(best[2])

    # Plates don't contain spaces/punctuation — strip anything OCR
    # might have picked up from smudges, bolts, or plate borders.
    cleaned_text = re.sub(r"[^A-Z0-9]", "", raw_text.upper())

    return cleaned_text, confidence, photo_filename
