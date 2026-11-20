"""Project paths and settings loading.

At Stage 0 this file only knows where things are and how to read the
optional .env file. Settings for the AI provider are added in later stages.
"""

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPROVED_DIR = PROJECT_ROOT / "data" / "approved"
CHECKSUM_FILE = APPROVED_DIR / "checksums.sha256"
ENV_FILE = PROJECT_ROOT / ".env"

# The six approved disaster files. Fire's Forest Fire content is a
# subsection inside fire.json, so there is no seventh file.
APPROVED_FILES = (
    "flood.json",
    "cyclone.json",
    "earthquake.json",
    "landslide.json",
    "tsunami.json",
    "fire.json",
)


def load_environment() -> bool:
    """Read the .env file if it exists. Returns True if a .env file was found."""
    return load_dotenv(ENV_FILE)
