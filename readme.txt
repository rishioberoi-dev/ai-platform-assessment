# CloudFactory AI Platform Assessment

## Overview

This repository contains a proof-of-concept reference pipeline built for the CloudFactory technical assessment. The solution focuses on the two core controls described in the brief:

1. preserving EXIF metadata integrity across image transfer and processing
2. enforcing 24-hour retention and deletion controls for images containing human faces

The pipeline also includes a controlled bridge-strip simulation to reproduce EXIF metadata loss and demonstrate metadata restoration.

---

## Problem Statement

The assessment scenario described two operational problems:

- the Transfer Bridge strips EXIF metadata such as GPS and timestamps, even though that metadata is required for downstream model functionality
- images containing human faces must be hard deleted within 24 hours

A second escalation issue was also identified:

- poor model quality on dark and blurry warehouse worker images compared with bright office-style imagery

This repository addresses the EXIF and privacy controls directly, and uses representative warehouse worker images as investigative evidence for the model-quality concern.

---

## What This Solution Does

For every image, the pipeline:

1. scans the source image
2. validates source EXIF metadata
3. scans for human faces
4. routes the image to either:
   - `approved`
   - `restricted_faces`
5. moves the image to its destination
6. validates EXIF again after transfer
7. compares source EXIF against processed EXIF
8. restores EXIF if the Transfer Bridge stripping bug is reproduced
9. creates a retention record for face-containing images
10. writes a manifest and audit log entry

The pipeline also includes a cleanup worker that deletes expired restricted images the next time the pipeline runs.

---

## Repository Structure

```text
cloudfactory-ai-platform-assessment/
├── models/
│   └── face_detector/
│       ├── deploy.prototxt.txt
│       └── res10_300x300_ssd_iter_140000.caffemodel
├── data/
│   ├── input/
│   ├── approved/
│   └── restricted_faces/
├── output/
│   ├── manifests/
│   └── logs/
├── src/
│   ├── audit_utils.py
│   ├── config.py
│   ├── exif_utils.py
│   ├── main.py
│   └── pii_retention.py
├── docs/
├── requirements.txt
└── README.md

---

Installation Notes:

1. Open a terminal in the repository root and run:

python -m pip install -r requirements.txt

2. Place your test images into: data/input

3. Then run: python src/main.py 

