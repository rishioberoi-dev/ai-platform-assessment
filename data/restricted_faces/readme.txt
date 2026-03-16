# Restricted Face Images

This folder contains images where a human face was detected.

Images routed here are subject to a **24-hour retention policy**.  
When a face is detected, the pipeline:

1. Moves the image into this folder.
2. Creates a retention manifest.
3. Records the deletion timestamp (`delete_after_utc`).

On subsequent pipeline runs, the cleanup worker scans retention manifests and **automatically deletes expired restricted images**.

This directory is intentionally empty in the repository so the pipeline can populate it during runtime.