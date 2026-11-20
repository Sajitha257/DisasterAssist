"""Loads the six approved JSON files safely.

Order of work (it stops and refuses to continue if any step fails):
  1. Check the SHA-256 checksum of every file.
  2. Read each file as strict UTF-8 and parse the JSON.
  3. Validate the structure and the safety rules.
Only data that passes all three steps is returned. The files are only READ.
They are never written, repaired or changed.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src import checksums
from src import config
from src.guide import expected as ex
from src.guide.validator import iter_instruction_groups, iter_instructions, validate_all

UTF8_BOM = b"\xef\xbb\xbf"


class ApprovedDataError(Exception):
    """Raised when the approved data cannot be trusted. `problems` lists why."""

    def __init__(self, problems: Iterable[str]):
        self.problems: List[str] = list(problems)
        shown = "; ".join(self.problems[:3])
        more = "" if len(self.problems) <= 3 else " (and %d more)" % (len(self.problems) - 3)
        super().__init__("Approved data is not valid: %s%s" % (shown, more))


def _reject_duplicate_keys(pairs):
    """json.loads normally keeps the LAST value of a repeated key silently."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key %r" % key)
        result[key] = value
    return result


def read_json_utf8(path: Path) -> dict:
    """Read one JSON file as strict UTF-8. Raises ApprovedDataError on any problem."""
    path = Path(path)
    name = path.name
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ApprovedDataError(["%s: cannot be read (%s)" % (name, error.__class__.__name__)])
    if raw.startswith(UTF8_BOM):
        raise ApprovedDataError(["%s: starts with a UTF-8 byte-order mark; the approved files have none" % name])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ApprovedDataError(["%s: is not valid UTF-8 (problem at byte %d)" % (name, error.start)])
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise ApprovedDataError(["%s: is not valid JSON (line %d, column %d: %s)" % (name, error.lineno, error.colno, error.msg)])
    except ValueError as error:
        raise ApprovedDataError(["%s: %s" % (name, error)])


@dataclass(frozen=True)
class ApprovedData:
    """The validated data of all six disasters. Treat it as read-only."""

    disasters: Dict[str, dict]

    @property
    def order(self) -> Tuple[str, ...]:
        return ex.DISASTER_ORDER

    def get(self, disaster_id: str) -> dict:
        return self.disasters[disaster_id]

    def source_map(self, disaster_id: str) -> Dict[str, dict]:
        """Map each source label (such as 'S2*') to its source_references entry."""
        return {s["display_label"]: s for s in self.disasters[disaster_id]["source_references"]}


def count_s2_items(data: dict) -> Tuple[int, int]:
    """Return (number of S2*-tagged instructions, how many of them have no item caveat)."""
    tagged = [item for _, item in iter_instructions(data) if "S2*" in item["source_tags"]]
    return len(tagged), sum(1 for item in tagged if item["caveat"] is None)


def summarise(approved: ApprovedData) -> Dict[str, Dict[str, int]]:
    """Count the parts of each file, from the loaded data (not from the expected table)."""
    summary: Dict[str, Dict[str, int]] = {}
    for disaster_id in approved.order:
        data = approved.get(disaster_id)
        counts: Dict[str, int] = {}
        for path, items in iter_instruction_groups(data):
            if path.startswith("subsections."):
                label = "sub:" + path[len("subsections."):]
            elif path.startswith("sections."):
                label = path[len("sections."):]
            else:
                label = path
            counts[label] = len(items)
        for key in ("known_conflicts", "limitations", "excluded_guidance", "source_references"):
            counts[key] = len(data[key])
        counts["instructions_total"] = sum(
            len(items) for path, items in iter_instruction_groups(data) if path != "common_preparedness"
        )
        counts["s2_tagged"], counts["s2_without_item_caveat"] = count_s2_items(data)
        summary[disaster_id] = counts
    return summary


def load_approved_data(
    approved_dir: Optional[Path] = None,
    checksum_file: Optional[Path] = None,
    verify_checksums: bool = True,
) -> ApprovedData:
    """Check, read and validate the six approved files.

    `verify_checksums=False` exists only for tests. The website must always
    use the default (True).
    """
    approved_dir = Path(approved_dir) if approved_dir is not None else config.APPROVED_DIR
    checksum_file = Path(checksum_file) if checksum_file is not None else config.CHECKSUM_FILE
    file_names = [d + ".json" for d in ex.DISASTER_ORDER]

    # Only the six approved files are allowed (no seventh file, no Forest Fire file).
    if approved_dir.is_dir():
        extra = sorted(p.name for p in approved_dir.glob("*.json") if p.name not in file_names)
        if extra:
            raise ApprovedDataError(["unexpected JSON file(s) in the approved folder: %s" % ", ".join(extra)])

    # Step 1: checksums.
    if verify_checksums:
        try:
            results = checksums.verify_checksums(approved_dir, checksum_file, file_names)
        except (OSError, ValueError) as error:
            raise ApprovedDataError(["checksum file cannot be used (%s)" % error.__class__.__name__])
        bad = ["%s: checksum result is %s" % (name, result) for name, result in results if result != checksums.OK]
        if bad:
            raise ApprovedDataError(bad)

    # Step 2: strict UTF-8 and JSON.
    loaded: Dict[str, dict] = {}
    load_problems: List[str] = []
    for disaster_id in ex.DISASTER_ORDER:
        try:
            loaded[disaster_id] = read_json_utf8(approved_dir / (disaster_id + ".json"))
        except ApprovedDataError as error:
            load_problems += error.problems
    if load_problems:
        raise ApprovedDataError(load_problems)

    # Step 3: structure and safety rules.
    problems = validate_all(loaded)
    if problems:
        raise ApprovedDataError(problems)
    return ApprovedData(disasters=loaded)
