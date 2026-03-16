from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2

from config import FACE_IMAGE_RETENTION_HOURS

# DNN face detector files
BASE_DIR = Path(__file__).resolve().parent.parent
FACE_DETECTOR_DIR = BASE_DIR / "models" / "face_detector"
FACE_PROTO_PATH = FACE_DETECTOR_DIR / "deploy.prototxt"  # keep as .txt if that is your real filename
FACE_MODEL_PATH = FACE_DETECTOR_DIR / "res10_300x300_ssd_iter_140000.caffemodel"

FACE_CONFIDENCE_THRESHOLD = 0.30
MIN_FACE_WIDTH = 30
MIN_FACE_HEIGHT = 30
MIN_FACE_AREA_RATIO = 0.002


def _load_face_net():
    if not FACE_PROTO_PATH.exists():
        raise FileNotFoundError(f"Missing face detector prototxt: {FACE_PROTO_PATH}")
    if not FACE_MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing face detector model: {FACE_MODEL_PATH}")

    return cv2.dnn.readNetFromCaffe(
        str(FACE_PROTO_PATH),
        str(FACE_MODEL_PATH),
    )


def _is_plausible_face_box(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    image_width: int,
    image_height: int,
) -> bool:
    width = max(0, end_x - start_x)
    height = max(0, end_y - start_y)

    if width < MIN_FACE_WIDTH or height < MIN_FACE_HEIGHT:
        return False

    aspect_ratio = width / float(height) if height else 0.0
    if not (0.65 <= aspect_ratio <= 1.5):
        return False

    box_area = width * height
    image_area = image_width * image_height
    area_ratio = box_area / float(image_area) if image_area else 0.0

    if area_ratio < MIN_FACE_AREA_RATIO:
        return False

    return True


def detect_faces(image_path: Path) -> dict:
    image = cv2.imread(str(image_path))
    if image is None:
        return {
            "faces_detected": False,
            "face_count": 0,
        }

    image_height, image_width = image.shape[:2]
    net = _load_face_net()

    blob = cv2.dnn.blobFromImage(
        image,
        1.0,
        (300, 300),
        (104.0, 177.0, 123.0),
        False,
        False,
    )

    net.setInput(blob)
    detections = net.forward()

    face_boxes = []

    for i in range(detections.shape[2]):
        confidence = float(detections[0, 0, i, 2])

        if confidence < FACE_CONFIDENCE_THRESHOLD:
            continue

        box = detections[0, 0, i, 3:7] * [
            image_width,
            image_height,
            image_width,
            image_height,
        ]
        start_x, start_y, end_x, end_y = box.astype("int")

        start_x = max(0, start_x)
        start_y = max(0, start_y)
        end_x = min(image_width, end_x)
        end_y = min(image_height, end_y)

        if _is_plausible_face_box(
            start_x,
            start_y,
            end_x,
            end_y,
            image_width,
            image_height,
        ):
            face_boxes.append((start_x, start_y, end_x, end_y, confidence))

    return {
        "faces_detected": len(face_boxes) > 0,
        "face_count": len(face_boxes),
    }


def build_retention_record(image_path: Path) -> dict:
    now = datetime.now(timezone.utc)
    delete_after = now + timedelta(hours=FACE_IMAGE_RETENTION_HOURS)

    return {
        "image_name": image_path.name,
        "image_path": str(image_path),
        "flagged_at_utc": now.isoformat(),
        "delete_after_utc": delete_after.isoformat(),
        "retention_hours": FACE_IMAGE_RETENTION_HOURS,
        "status": "restricted_face_retention",
        "deleted": False,
        "deleted_at_utc": None,
    }


def save_retention_record(record: dict, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)


def should_delete_now(delete_after_utc: str) -> bool:
    delete_after = datetime.fromisoformat(delete_after_utc)
    now = datetime.now(timezone.utc)
    return now >= delete_after


def delete_expired_restricted_images(manifests_dir: Path) -> list[dict]:
    """
    Scan retention manifests and hard-delete any expired restricted image.
    Returns a list of deletion results for logging/audit.
    """
    results: list[dict] = []

    for retention_manifest in manifests_dir.glob("*_retention.json"):
        try:
            with retention_manifest.open("r", encoding="utf-8") as handle:
                record = json.load(handle)
        except Exception:
            results.append(
                {
                    "retention_manifest": str(retention_manifest),
                    "status": "error",
                    "message": "Could not read retention manifest.",
                }
            )
            continue

        if record.get("deleted") is True:
            continue

        delete_after_utc = record.get("delete_after_utc")
        image_path_str = record.get("image_path")

        if not delete_after_utc or not image_path_str:
            results.append(
                {
                    "retention_manifest": str(retention_manifest),
                    "status": "error",
                    "message": "Retention manifest missing delete_after_utc or image_path.",
                }
            )
            continue

        if not should_delete_now(delete_after_utc):
            continue

        image_path = Path(image_path_str)
        image_deleted = False

        try:
            if image_path.exists():
                image_path.unlink()
                image_deleted = True
        except Exception as exc:
            results.append(
                {
                    "retention_manifest": str(retention_manifest),
                    "image_path": str(image_path),
                    "status": "error",
                    "message": f"Failed to delete image: {exc}",
                }
            )
            continue

        record["deleted"] = True
        record["deleted_at_utc"] = datetime.now(timezone.utc).isoformat()
        record["status"] = "deleted_after_retention_window"
        record["image_deleted"] = image_deleted

        try:
            with retention_manifest.open("w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2)
        except Exception as exc:
            results.append(
                {
                    "retention_manifest": str(retention_manifest),
                    "image_path": str(image_path),
                    "status": "error",
                    "message": f"Image deleted but failed to update retention manifest: {exc}",
                }
            )
            continue

        results.append(
            {
                "retention_manifest": str(retention_manifest),
                "image_path": str(image_path),
                "status": "deleted",
                "message": "Expired restricted image deleted successfully.",
            }
        )

    return results