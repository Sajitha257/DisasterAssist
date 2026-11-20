"""SHA-256 checksum helpers.

A checksum is a fingerprint of a file. If even one character in a file
changes, its fingerprint changes. We use this to prove that the six approved
JSON files have not been modified.
"""

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# Possible results for each file.
OK = "OK"
MISMATCH = "MISMATCH"
MISSING_FILE = "MISSING_FILE"
NOT_IN_CHECKSUM_FILE = "NOT_IN_CHECKSUM_FILE"


def sha256_of_file(path: Path) -> str:
    """Return the SHA-256 fingerprint of a file as lowercase hex text."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_checksum_file(checksum_file: Path) -> Dict[str, str]:
    """Read a checksum file. Each line is: <fingerprint>  <file name>."""
    expected: Dict[str, str] = {}
    text = checksum_file.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ValueError("Bad line in checksum file: " + line)
        fingerprint, name = parts
        expected[name.lstrip("*").strip()] = fingerprint.lower()
    return expected


def verify_checksums(
    directory: Path, checksum_file: Path, file_names: Iterable[str]
) -> List[Tuple[str, str]]:
    """Compare each named file in `directory` with the checksum file.

    Returns a list of (file name, result) pairs. The result is one of
    OK, MISMATCH, MISSING_FILE or NOT_IN_CHECKSUM_FILE.
    """
    expected = read_checksum_file(checksum_file)
    results: List[Tuple[str, str]] = []
    for name in file_names:
        path = directory / name
        if not path.is_file():
            results.append((name, MISSING_FILE))
        elif name not in expected:
            results.append((name, NOT_IN_CHECKSUM_FILE))
        elif sha256_of_file(path) == expected[name]:
            results.append((name, OK))
        else:
            results.append((name, MISMATCH))
    return results
