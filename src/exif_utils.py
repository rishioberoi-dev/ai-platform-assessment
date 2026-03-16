from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

RELEVANT_EXIF_FIELDS = {
    "DateTime",
    "DateTimeOriginal",
    "DateTimeDigitized",
    "GPSInfo",
    "Make",
    "Model",
}

# pseudo:
# build reverse lookup so we can write EXIF fields back by tag id later
TAG_NAME_TO_ID = {
    name: tag_id
    for tag_id, name in ExifTags.TAGS.items()
}


def extract_exif_metadata(image_path: Path) -> dict[str, Any]:
    # pseudo:
    # open image and extract only EXIF fields relevant to this assessment
    # if image has no EXIF or cannot be read, return empty dict
    try:
        with Image.open(image_path) as img:
            raw_exif = img.getexif()

            if not raw_exif:
                return {}

            readable_exif: dict[str, Any] = {}

            for tag_id, value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))

                if tag_name in RELEVANT_EXIF_FIELDS:
                    readable_exif[tag_name] = value

            return readable_exif

    except Exception:
        return {}


def extract_required_exif_fields(exif_data: dict[str, Any]) -> dict[str, Any]:
    # pseudo:
    # preserve only the minimum EXIF fields that matter for the brief:
    # timestamps + GPS + a couple of camera identity fields for traceability
    required_fields = (
        "DateTime",
        "DateTimeOriginal",
        "DateTimeDigitized",
        "GPSInfo",
        "Make",
        "Model",
    )

    return {
        field: exif_data[field]
        for field in required_fields
        if field in exif_data
    }


def has_required_context_fields(exif_data: dict[str, Any]) -> bool:
    # pseudo:
    # required context means at least one timestamp field or GPSInfo
    has_timestamp = any(
        field in exif_data
        for field in ("DateTime", "DateTimeOriginal", "DateTimeDigitized")
    )
    has_gps = "GPSInfo" in exif_data

    return has_timestamp or has_gps


def summarize_exif_status(exif_data: dict[str, Any]) -> dict[str, Any]:
    # pseudo:
    # compact EXIF summary for manifests, comparisons, and terminal output
    timestamp_fields = ("DateTime", "DateTimeOriginal", "DateTimeDigitized")

    timestamp_fields_found = [
        field for field in timestamp_fields if field in exif_data
    ]

    timestamp_values = {
        field: str(exif_data[field])
        for field in timestamp_fields
        if field in exif_data
    }

    gps_present = "GPSInfo" in exif_data
    gps_value = str(exif_data["GPSInfo"]) if gps_present else None

    return {
        "exif_present": bool(exif_data),
        "required_context_present": has_required_context_fields(exif_data),
        "timestamp_fields_found": timestamp_fields_found,
        "timestamp_values": timestamp_values,
        "gps_present": gps_present,
        "gps_value": gps_value,
        "fields_found": sorted(exif_data.keys()),
    }


def restore_required_exif_fields(
    image_path: Path,
    required_exif_fields: dict[str, Any],
) -> bool:
    # pseudo:
    # try to restore required EXIF fields back onto the processed artifact
    # this is the actual metadata-preservation fix rather than just bug detection
    #
    # note:
    # EXIF write-back is most reliable on JPEG/WebP/TIFF-style files.
    # PNG may not preserve EXIF consistently across tools, so this function
    # may return False there without meaning the logic is wrong.

    if not required_exif_fields:
        return False

    try:
        with Image.open(image_path) as img:
            exif = img.getexif()

            # pseudo:
            # write back the preserved required fields using EXIF tag ids
            for field_name, field_value in required_exif_fields.items():
                tag_id = TAG_NAME_TO_ID.get(field_name)
                if tag_id is not None:
                    exif[tag_id] = field_value

            save_kwargs = {}

            # pseudo:
            # JPEG/TIFF/WebP usually support passing EXIF bytes back on save
            if img.format in {"JPEG", "JPG", "TIFF", "WEBP"}:
                save_kwargs["exif"] = exif.tobytes()
            else:
                # pseudo:
                # for formats like PNG, EXIF persistence is not dependable in this path
                return False

            img.save(image_path, **save_kwargs)
            return True

    except Exception:
        # pseudo:
        # GPSInfo can sometimes be awkward to write back depending on how it was stored,
        # so do one fallback pass with only timestamp / camera identity fields.
        try:
            fallback_fields = {
                key: value
                for key, value in required_exif_fields.items()
                if key != "GPSInfo"
            }

            if not fallback_fields:
                return False

            with Image.open(image_path) as img:
                exif = img.getexif()

                for field_name, field_value in fallback_fields.items():
                    tag_id = TAG_NAME_TO_ID.get(field_name)
                    if tag_id is not None:
                        exif[tag_id] = field_value

                if img.format not in {"JPEG", "JPG", "TIFF", "WEBP"}:
                    return False

                img.save(image_path, exif=exif.tobytes())
                return True

        except Exception:
            return False