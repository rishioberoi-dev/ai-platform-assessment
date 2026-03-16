# Approved Images

This folder contains images that passed the processing pipeline.

Images are routed here when:
- no human faces are detected
- EXIF integrity checks pass
- the image does not require restricted retention

During pipeline execution, images from `data/input/` that meet these conditions are copied into this folder.

This directory is intentionally empty in the repository so the pipeline can populate it during runtime.