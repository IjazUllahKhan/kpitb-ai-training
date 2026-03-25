"""
detector.py - PPE Detection Module
Handles YOLO model loading and inference with proper error handling.
"""

import logging
import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# Class names in model order
CLASS_NAMES = [
    'Excavator', 'Gloves', 'Hardhat', 'Ladder', 'Mask',
    'NO-Hardhat', 'NO-Mask', 'NO-Safety Vest', 'Person',
    'SUV', 'Safety Cone', 'Safety Vest', 'bus', 'dump truck',
    'fire hydrant', 'machinery', 'mini-van', 'sedan', 'semi',
    'trailer', 'truck and trailer', 'truck', 'van', 'vehicle',
    'wheel loader'
]

# PPE violation classes (NO-* prefixed)
VIOLATION_CLASSES = {'NO-Hardhat', 'NO-Mask', 'NO-Safety Vest'}

# Safe PPE classes
SAFE_PPE_CLASSES = {'Hardhat', 'Mask', 'Safety Vest', 'Gloves'}

# Drawing colors (BGR)
COLOR_VIOLATION = (0, 0, 220)      # Red
COLOR_SAFE_PPE  = (0, 200, 0)      # Green
COLOR_OTHER     = (200, 140, 0)    # Blue/orange for vehicles, persons etc.

CONFIDENCE_THRESHOLD = 0.45


class Detector:
    """YOLO-based PPE detector with bounding box drawing."""

    def __init__(self, model_path: str = "model/best.pt"):
        logger.info(f"Loading YOLO model from: {model_path}")
        try:
            self.model = YOLO(model_path)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def detect(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        """
        Run PPE detection on a single BGR image frame.
        Returns (annotated_img, status_string).
        status_string is "Violation" or "Safe".
        """
        if img is None or img.size == 0:
            logger.warning("detect() received an empty frame.")
            return img, "Unknown"

        try:
            results = self.model(img, verbose=False)[0]
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return img, "Error"

        violation = False

        for box in results.boxes:
            conf = float(box.conf[0])
            if conf < CONFIDENCE_THRESHOLD:
                continue

            cls_idx = int(box.cls[0])
            if cls_idx >= len(CLASS_NAMES):
                continue

            label = CLASS_NAMES[cls_idx]
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            if label in VIOLATION_CLASSES:
                color = COLOR_VIOLATION
                violation = True
            elif label in SAFE_PPE_CLASSES:
                color = COLOR_SAFE_PPE
            else:
                color = COLOR_OTHER

            # Draw bounding box
            thickness = 2
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

            # Draw corner accent (top-left, top-right, bottom-left, bottom-right)
            corner_len = max(10, min(20, (x2 - x1) // 5))
            cv2.line(img, (x1, y1), (x1 + corner_len, y1), color, thickness + 1)
            cv2.line(img, (x1, y1), (x1, y1 + corner_len), color, thickness + 1)
            cv2.line(img, (x2, y1), (x2 - corner_len, y1), color, thickness + 1)
            cv2.line(img, (x2, y1), (x2, y1 + corner_len), color, thickness + 1)
            cv2.line(img, (x1, y2), (x1 + corner_len, y2), color, thickness + 1)
            cv2.line(img, (x1, y2), (x1, y2 - corner_len), color, thickness + 1)
            cv2.line(img, (x2, y2), (x2 - corner_len, y2), color, thickness + 1)
            cv2.line(img, (x2, y2), (x2, y2 - corner_len), color, thickness + 1)

            # Label background + text
            text = f"{label}  {conf:.2f}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.55
            font_thickness = 1
            (tw, th), baseline = cv2.getTextSize(text, font, font_scale, font_thickness)
            label_y = max(y1 - 6, th + 4)
            cv2.rectangle(img, (x1, label_y - th - baseline - 2),
                          (x1 + tw + 4, label_y + baseline), color, -1)
            cv2.putText(img, text, (x1 + 2, label_y - baseline),
                        font, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)

        status = "Violation" if violation else "Safe"
        return img, status
