from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

INPUT_DIR = DATA_DIR / "input"
APPROVED_DIR = DATA_DIR / "approved"
RESTRICTED_FACES_DIR = DATA_DIR / "restricted_faces"

MANIFESTS_DIR = OUTPUT_DIR / "manifests"
LOGS_DIR = OUTPUT_DIR / "logs"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

FACE_IMAGE_RETENTION_HOURS = 24