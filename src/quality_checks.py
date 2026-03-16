from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from config import MIN_BLUR_VARIANCE, MIN_BRIGHTNESS_SCORE


def calculate_brightness_score(image_path: Path) -> float:
    """
    Return average grayscale brightness from 0-255.
    Lower values suggest dark images.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        return 0.0

    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(np.mean(grayscale))


def calculate_blur_variance(image_path: Path) -> float:
    """
    Return Laplacian variance.
    Lower values suggest a blurrier image.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        return 0.0

    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(grayscale, cv2.CV_64F).var())


def assess_image_quality(image_path: Path) -> dict:
    """
    Check whether the image passes simple brightness and blur thresholds.
    """
    brightness_score = calculate_brightness_score(image_path)
    blur_variance = calculate_blur_variance(image_path)

    reasons = []

    if brightness_score < MIN_BRIGHTNESS_SCORE:
        reasons.append("low_brightness")

    if blur_variance < MIN_BLUR_VARIANCE:
        reasons.append("blurry_image")

    return {
        "passed": len(reasons) == 0,
        "brightness_score": round(brightness_score, 2),
        "blur_variance": round(blur_variance, 2),
        "failure_reasons": reasons,
    }