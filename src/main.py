from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from audit_utils import append_audit_log
from config import (
    APPROVED_DIR,
    INPUT_DIR,
    MANIFESTS_DIR,
    RESTRICTED_FACES_DIR,
    SUPPORTED_EXTENSIONS,
)
from exif_utils import (
    extract_exif_metadata,
    extract_required_exif_fields,
    restore_required_exif_fields,
    summarize_exif_status,
)
from pii_retention import (
    build_retention_record,
    delete_expired_restricted_images,
    detect_faces,
    save_retention_record,
)


def ensure_directories() -> None:
    for directory in [
        INPUT_DIR,
        APPROVED_DIR,
        RESTRICTED_FACES_DIR,
        MANIFESTS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def copy_processed_artifact(source: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / source.name
    shutil.copy2(source, destination_path)
    return destination_path


def simulate_bridge_exif_stripping(image_path: Path) -> bool:
    # demo-only helper:
    # if filename contains "bridge_strip", resave without EXIF to reproduce the bug
    if "bridge_strip" not in image_path.stem.lower():
        return False

    try:
        with Image.open(image_path) as img:
            if img.format in {"JPEG", "JPG"}:
                img.save(image_path, format=img.format)
                return True
            return False
    except Exception:
        return False


def write_manifest(image_name: str, manifest: dict) -> Path:
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFESTS_DIR / f"{Path(image_name).stem}.json"

    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return manifest_path


def determine_exif_integrity(
    source_exif_summary: dict,
    processed_exif_summary: dict,
) -> tuple[str, str]:
    source_has_required = source_exif_summary["required_context_present"]
    processed_has_required = processed_exif_summary["required_context_present"]

    # both have required GPS/timestamp context
    if source_has_required and processed_has_required:
        return (
            "exif_preserved",
            "EXIF metadata integrity verification completed successfully.",
        )

    # both lack required context, but processed matches source
    if not source_has_required and not processed_has_required:
        return (
            "exif_preserved",
            "EXIF metadata integrity verification completed successfully. "
            "Source and processed image match, although required GPS/timestamp context was absent at source.",
        )

    # source had required EXIF but processed lost it
    return (
        "exif_lost_in_processing",
        "EXIF metadata integrity verification failed: required metadata was present in the source image but missing after processing.",
    )


def format_timestamp_values(exif_summary: dict) -> str:
    timestamp_values = exif_summary.get("timestamp_values", {})
    if not timestamp_values:
        return "none"
    return "; ".join(f"{k}={v}" for k, v in timestamp_values.items())


def format_gps_value(exif_summary: dict) -> str:
    gps_present = exif_summary.get("gps_present", False)
    gps_value = exif_summary.get("gps_value")
    if gps_present and gps_value is not None:
        return str(gps_value)
    return "none"


def print_step(message: str) -> None:
    print(message)


def process_image(image_path: Path) -> dict:
    print_step("\n" + "=" * 110)
    print_step(f"Scanning picture: {image_path.name}")

    print_step(
        "Step 1: Validating EXIF metadata on source image. "
        "Required fields for model functionality: GPS and/or timestamp."
    )
    source_exif_data = extract_exif_metadata(image_path)
    source_exif_summary = summarize_exif_status(source_exif_data)
    preserved_required_exif = extract_required_exif_fields(source_exif_data)

    source_timestamp_text = format_timestamp_values(source_exif_summary)
    source_gps_text = format_gps_value(source_exif_summary)

    print_step(
        f"Source EXIF scan result -> timestamp_values: {source_timestamp_text} | gps_value: {source_gps_text}"
    )

    if source_exif_summary["required_context_present"]:
        print_step(
            "Source EXIF validation completed successfully. Required metadata is present for downstream model use."
        )
    else:
        print_step(
            "Source EXIF validation completed. Required GPS/timestamp metadata is absent at source, "
            "but this image will still continue through routing and integrity comparison."
        )

    print_step(
        "Step 2: Scanning for the privacy rule. "
        "All images with human faces must be hard deleted within 24 hours."
    )
    face_result = detect_faces(image_path)
    faces_detected = face_result["faces_detected"]

    if faces_detected:
        print_step("Face detection result -> YES")
    else:
        print_step("Face detection result -> NO")

    status = "approved"
    destination_dir = APPROVED_DIR
    reasons: list[str] = []

    if faces_detected:
        status = "restricted_face_retention"
        destination_dir = RESTRICTED_FACES_DIR
        reasons.append("face_detected")
        print_step(
            "Routing decision -> Image contains a face. Moving image to restricted_faces for 24-hour retention control."
        )
    else:
        print_step("Routing decision -> No face detected. Moving image to approved.")

    processed_path = copy_processed_artifact(image_path, destination_dir)
    print_step(f"Image moved successfully -> {processed_path}")

    bridge_strip_simulated = simulate_bridge_exif_stripping(processed_path)
    if bridge_strip_simulated:
        reasons.append("bridge_exif_strip_simulated")
        print_step(
            "Bridge simulation -> EXIF stripping event intentionally reproduced for demo validation."
        )

    print_step(
        "Step 3: Validating EXIF metadata on the moved image to verify metadata was not lost during transfer/translation."
    )
    processed_exif_data = extract_exif_metadata(processed_path)
    processed_exif_summary = summarize_exif_status(processed_exif_data)

    processed_timestamp_text = format_timestamp_values(processed_exif_summary)
    processed_gps_text = format_gps_value(processed_exif_summary)

    print_step(
        f"Processed image EXIF scan result -> timestamp_values: {processed_timestamp_text} | gps_value: {processed_gps_text}"
    )

    exif_integrity_status, exif_integrity_message = determine_exif_integrity(
        source_exif_summary,
        processed_exif_summary,
    )

    source_matches_processed = (
        source_exif_summary.get("timestamp_values", {})
        == processed_exif_summary.get("timestamp_values", {})
        and source_exif_summary.get("gps_value")
        == processed_exif_summary.get("gps_value")
    )

    print_step(
        f"EXIF metadata comparison -> matching source and processed metadata: {'YES' if source_matches_processed else 'NO'}"
    )

    metadata_restoration_applied = False
    metadata_restoration_succeeded = False

    if exif_integrity_status == "exif_lost_in_processing":
        print_step(
            "EXIF integrity verification failed after processing. Required metadata appears to have been stripped during bridge transfer."
        )
        print_step(
            "Applying metadata restoration control using preserved source EXIF system record."
        )

        metadata_restoration_applied = True
        restore_ok = restore_required_exif_fields(processed_path, preserved_required_exif)

        processed_exif_data = extract_exif_metadata(processed_path)
        processed_exif_summary = summarize_exif_status(processed_exif_data)

        processed_timestamp_text = format_timestamp_values(processed_exif_summary)
        processed_gps_text = format_gps_value(processed_exif_summary)

        exif_integrity_status, exif_integrity_message = determine_exif_integrity(
            source_exif_summary,
            processed_exif_summary,
        )

        metadata_restoration_succeeded = (
            restore_ok and exif_integrity_status == "exif_preserved"
        )

        if metadata_restoration_succeeded:
            reasons.append("exif_restored_after_processing")
            print_step(
                "Metadata restoration completed successfully. Required EXIF fields were restored onto the processed artifact."
            )
            print_step(
                f"Restored image EXIF scan result -> timestamp_values: {processed_timestamp_text} | gps_value: {processed_gps_text}"
            )
        else:
            reasons.append("exif_restoration_failed")
            print_step(
                "Metadata restoration failed. Required EXIF fields could not be fully restored onto the processed artifact."
            )
    else:
        print_step(exif_integrity_message)

    manifest = {
        "image_name": image_path.name,
        "processed_at_utc": datetime.now(UTC).isoformat(),
        "status": status,
        "final_path": str(processed_path),
        "reasons": reasons,
        "source_exif_summary": source_exif_summary,
        "processed_exif_summary": processed_exif_summary,
        "preserved_required_exif": preserved_required_exif,
        "exif_integrity_status": exif_integrity_status,
        "exif_integrity_message": exif_integrity_message,
        "bridge_strip_simulated": bridge_strip_simulated,
        "metadata_restoration_applied": metadata_restoration_applied,
        "metadata_restoration_succeeded": metadata_restoration_succeeded,
        "face_result": face_result,
    }

    if faces_detected:
        print_step(
            "24-hour retention control -> Creating retention record because a face was detected."
        )
        retention_record = build_retention_record(processed_path)
        retention_manifest_path = MANIFESTS_DIR / f"{image_path.stem}_retention.json"
        save_retention_record(retention_record, retention_manifest_path)
        manifest["retention_record"] = retention_record
        manifest["retention_manifest_path"] = str(retention_manifest_path)
        print_step(f"Retention record created -> {retention_manifest_path}")

    manifest_path = write_manifest(image_path.name, manifest)
    manifest["manifest_path"] = str(manifest_path)
    print_step(f"Manifest written -> {manifest_path}")

    append_audit_log(
        event_type="image_processed",
        message=(
            f"{image_path.name} processed with status '{status}', "
            f"EXIF result '{exif_integrity_status}', "
            f"bridge_strip_simulated={bridge_strip_simulated}, "
            f"metadata_restoration_applied={metadata_restoration_applied}, "
            f"metadata_restoration_succeeded={metadata_restoration_succeeded}"
        ),
        metadata={
            "image_name": image_path.name,
            "status": status,
            "reasons": reasons,
            "exif_integrity_status": exif_integrity_status,
            "bridge_strip_simulated": bridge_strip_simulated,
            "metadata_restoration_applied": metadata_restoration_applied,
            "metadata_restoration_succeeded": metadata_restoration_succeeded,
            "manifest_path": str(manifest_path),
        },
    )
    print_step("Audit log updated successfully.")

    print_step(
        f"Final result -> status: {status} | EXIF integrity: {exif_integrity_status} | reasons: {', '.join(reasons) if reasons else 'none'}"
    )

    return manifest


def main() -> None:
    ensure_directories()

    # Step 0: enforce 24-hour hard deletion for expired restricted images
    deletion_results = delete_expired_restricted_images(MANIFESTS_DIR)

    if deletion_results:
        print("\nRunning retention cleanup worker...")
        for deletion_result in deletion_results:
            print(
                f"Retention cleanup -> {deletion_result['status']} | "
                f"{deletion_result.get('image_path', deletion_result.get('retention_manifest', 'unknown'))} | "
                f"{deletion_result['message']}"
            )

            append_audit_log(
                event_type="retention_cleanup",
                message=deletion_result["message"],
                metadata=deletion_result,
            )

    input_images = [
        path
        for path in INPUT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not input_images:
        print(f"No supported image files found in: {INPUT_DIR}")
        return

    summary = {
        "processed": 0,
        "approved": 0,
        "restricted_face_retention": 0,
        "exif_preserved": 0,
        "exif_lost_in_processing": 0,
    }

    print("\nStarting image processing pipeline...")
    print(f"Total images discovered: {len(input_images)}")

    for image_path in sorted(input_images):
        result = process_image(image_path)
        summary["processed"] += 1
        summary[result["status"]] += 1
        summary[result["exif_integrity_status"]] += 1

    print("\n" + "=" * 110)
    print("PIPELINE SUMMARY")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()