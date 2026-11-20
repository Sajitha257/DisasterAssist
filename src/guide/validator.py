"""Validation of the six approved JSON files.

The validator only CHECKS the data. It never changes it. It collects every
problem it finds (it does not stop at the first one) and returns them as a
list of plain-English messages. An empty list means the data is valid.
"""

import re
from typing import Any, Dict, Iterator, List, Tuple

from src.guide import expected as ex
from src.guide import limitations

AllData = Dict[str, Any]  # disaster id ("flood") -> the loaded JSON dictionary

CONFLICT_ID_PATTERN = re.compile(r"\b[A-Z]+-[A-Z]-\d{3}\b|\bC[1-8]\b")


# ---------------------------------------------------------------- small helpers
def _filled(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _check_keys(problems: List[str], where: str, obj: Any, keys: Tuple[str, ...]) -> bool:
    """Check that `obj` is a dictionary with exactly the given keys."""
    if not isinstance(obj, dict):
        problems.append("%s: must be an object" % where)
        return False
    missing = [k for k in keys if k not in obj]
    extra = [k for k in obj if k not in keys]
    for key in missing:
        problems.append("%s: missing required key '%s'" % (where, key))
    for key in extra:
        problems.append("%s: unexpected key '%s' (schema must not change)" % (where, key))
    return not missing and not extra


def iter_instruction_groups(data: dict) -> Iterator[Tuple[str, list]]:
    """Yield (path, list of instruction items) for every group of instructions.

    Includes Before/During/After, subsection groups (Forest Fire, tsunami
    bulletin levels) and the common preparedness items. Missing or damaged
    parts are skipped quietly (the validator reports them separately).
    """
    sections = data.get("sections")
    if isinstance(sections, dict):
        for name in ex.SECTION_NAMES:
            if isinstance(sections.get(name), list):
                yield "sections.%s" % name, sections[name]
    subsections = data.get("subsections")
    if isinstance(subsections, list):
        for sub in subsections:
            if isinstance(sub, dict) and isinstance(sub.get("sections"), dict):
                for group, items in sub["sections"].items():
                    if isinstance(items, list):
                        yield "subsections.%s.%s" % (sub.get("subsection_id"), group), items
    if isinstance(data.get("common_preparedness"), list):
        yield "common_preparedness", data["common_preparedness"]


def iter_instructions(data: dict) -> Iterator[Tuple[str, dict]]:
    """Yield (path, instruction) for every instruction item that is an object."""
    for path, items in iter_instruction_groups(data):
        for item in items:
            if isinstance(item, dict):
                yield path, item


def _check_id_sequence(
    problems: List[str], where: str, ids: List[Any], stems: Tuple[str, ...]
) -> None:
    """IDs must look like STEM-001 and count up 1, 2, 3... for each stem."""
    numbers: Dict[str, List[int]] = {stem: [] for stem in stems}
    for item_id in ids:
        matched = False
        if isinstance(item_id, str):
            for stem in stems:
                found = re.fullmatch(re.escape(stem) + r"-(\d{3})", item_id)
                if found:
                    numbers[stem].append(int(found.group(1)))
                    matched = True
                    break
        if not matched:
            problems.append("%s: ID %r does not match the allowed pattern %s" % (where, item_id, " or ".join(s + "-NNN" for s in stems)))
    for stem, found_numbers in numbers.items():
        if found_numbers and found_numbers != list(range(1, len(found_numbers) + 1)):
            problems.append(
                "%s: IDs for %s are not numbered 001, 002, 003... without gaps or repeats (found %s)"
                % (where, stem, found_numbers)
            )


def _check_instruction(
    problems: List[str], where: str, item: Any, labels: set, allow_empty_tags: bool = False
) -> None:
    """Check one instruction object."""
    if not _check_keys(problems, where, item, ex.INSTRUCTION_KEYS):
        return
    if not _filled(item["instruction_id"]):
        problems.append("%s: instruction_id must be non-empty text" % where)
    if not _filled(item["text"]):
        problems.append("%s: text must be non-empty text" % where)
    caveat = item["caveat"]
    if caveat is not None and not _filled(caveat):
        problems.append("%s: caveat must be null or non-empty text" % where)
    _check_tags(problems, where, item["source_tags"], labels, allow_empty=False)
    if isinstance(item["source_tags"], list) and not item["source_tags"]:
        if item["instruction_id"] not in ex.EMPTY_TAG_ALLOWED_IDS:
            problems.append("%s: has no source tags (only %s may be untagged)" % (where, ", ".join(ex.EMPTY_TAG_ALLOWED_IDS)))
        elif caveat is None:
            problems.append("%s: an untagged instruction must keep its caveat" % where)


def _check_tags(problems: List[str], where: str, tags: Any, labels: set, allow_empty: bool) -> None:
    """Every source tag must be text that exists in this file's source register."""
    if not isinstance(tags, list):
        problems.append("%s: source_tags must be a list" % where)
        return
    if not tags and not allow_empty:
        return  # empty lists are judged by the caller
    if len(set(t for t in tags if isinstance(t, str))) != len(tags):
        problems.append("%s: source_tags contains a repeated tag" % where)
    for tag in tags:
        if not isinstance(tag, str):
            problems.append("%s: source tag %r must be text" % (where, tag))
        elif tag not in labels:
            problems.append("%s: source tag %r is not in this file's source_references" % (where, tag))


# ------------------------------------------------------------ one-file validation
def validate_disaster(disaster_id: str, data: Any) -> List[str]:
    """Validate one disaster file. Returns a list of problems."""
    file_name = disaster_id + ".json"
    problems: List[str] = []

    def add(path: str, message: str) -> None:
        problems.append("%s: %s: %s" % (file_name, path, message))

    if not isinstance(data, dict):
        return ["%s: the file must contain a JSON object" % file_name]

    # --- top level
    sub_problems: List[str] = []
    _check_keys(sub_problems, "top level", data, ex.TOP_LEVEL_KEYS)
    problems += ["%s: %s" % (file_name, p) for p in sub_problems]

    if data.get("disaster_id") != disaster_id:
        add("disaster_id", "expected %r, found %r" % (disaster_id, data.get("disaster_id")))
    if data.get("disaster_name") != ex.DISASTER_NAMES.get(disaster_id):
        add("disaster_name", "expected %r, found %r" % (ex.DISASTER_NAMES.get(disaster_id), data.get("disaster_name")))
    if data.get("project_notice") != ex.APPROVED_PROJECT_NOTICE:
        add("project_notice", "does not match the approved project notice")
    if data.get("emergency_number") != ex.APPROVED_EMERGENCY_NUMBER:
        add("emergency_number", "must be %r, found %r" % (ex.APPROVED_EMERGENCY_NUMBER, data.get("emergency_number")))

    prefix = disaster_id.upper()
    expected_counts = ex.EXPECTED_COUNTS[disaster_id]

    # --- source register (needed first, because tags are checked against it)
    labels: set = set()
    sources = data.get("source_references")
    if not isinstance(sources, list):
        add("source_references", "must be a list")
        sources = []
    ids_seen: List[str] = []
    for index, source in enumerate(sources):
        where = "source_references[%d]" % index
        sub_problems = []
        if _check_keys(sub_problems, where, source, ex.SOURCE_KEYS):
            for key in ex.SOURCE_KEYS:
                if key == "attribution_note":
                    # A note may be null (some sources need none) but never empty text.
                    if source[key] is not None and not _filled(source[key]):
                        sub_problems.append("%s: 'attribution_note' must be null or non-empty text" % where)
                elif not _filled(source[key]):
                    sub_problems.append("%s: '%s' must be non-empty text" % (where, key))
            if _filled(source["display_label"]) and _filled(source["source_id"]):
                if not source["display_label"].startswith(source["source_id"]):
                    sub_problems.append("%s: display_label %r does not start with source_id %r" % (where, source["display_label"], source["source_id"]))
                if source["display_label"] in labels:
                    sub_problems.append("%s: display_label %r is repeated" % (where, source["display_label"]))
                labels.add(source["display_label"])
                ids_seen.append(source["source_id"])
            if _filled(source["url"]) and not source["url"].startswith("https://"):
                sub_problems.append("%s: url must start with https://" % where)
        problems += ["%s: %s" % (file_name, p) for p in sub_problems]
    if len(set(ids_seen)) != len(ids_seen):
        add("source_references", "a source_id is repeated")
    if len(sources) != expected_counts["source_references"]:
        add("source_references", "expected %d sources, found %d" % (expected_counts["source_references"], len(sources)))

    # --- Before / During / After
    sections = data.get("sections")
    if not isinstance(sections, dict):
        add("sections", "must be an object")
        sections = {}
    else:
        if list(sections.keys()) != list(ex.SECTION_NAMES):
            add("sections", "must contain exactly before, during, after (found %s)" % list(sections.keys()))
    for name in ex.SECTION_NAMES:
        items = sections.get(name)
        path = "sections.%s" % name
        if not isinstance(items, list):
            add(path, "must be a list")
            continue
        for index, item in enumerate(items):
            sub_problems = []
            _check_instruction(sub_problems, "%s[%d]" % (path, index), item, labels)
            problems += ["%s: %s" % (file_name, p) for p in sub_problems]
        if len(items) != expected_counts[name]:
            add(path, "expected %d instructions, found %d" % (expected_counts[name], len(items)))
        letters = ex.SECTION_ID_LETTERS[name] + ex.EXTRA_LETTERS.get((disaster_id, name), ())
        stems = tuple("%s-%s" % (prefix, letter) for letter in letters)
        sub_problems = []
        _check_id_sequence(sub_problems, path, [i.get("instruction_id") if isinstance(i, dict) else None for i in items], stems)
        problems += ["%s: %s" % (file_name, p) for p in sub_problems]

    # --- subsections (Forest Fire under Fire; tsunami bulletin levels)
    subsections = data.get("subsections")
    wanted_sub = ex.SUBSECTION_EXPECTED.get(disaster_id)
    if not isinstance(subsections, list):
        add("subsections", "must be a list")
        subsections = []
    if wanted_sub is None:
        if subsections:
            add("subsections", "this disaster must have no subsections")
    else:
        if len(subsections) != 1:
            add("subsections", "expected exactly 1 subsection (%s), found %d" % (wanted_sub["subsection_name"], len(subsections)))
        for sub in subsections[:1]:
            where = "subsections[0]"
            sub_problems = []
            if _check_keys(sub_problems, where, sub, ex.SUBSECTION_KEYS):
                if sub["subsection_id"] != wanted_sub["subsection_id"]:
                    sub_problems.append("%s: subsection_id must be %r" % (where, wanted_sub["subsection_id"]))
                if sub["subsection_name"] != wanted_sub["subsection_name"]:
                    sub_problems.append("%s: subsection_name must be %r" % (where, wanted_sub["subsection_name"]))
                if not _filled(sub["description"]) or wanted_sub["description_must_contain"] not in sub["description"]:
                    sub_problems.append("%s: description must contain %r" % (where, wanted_sub["description_must_contain"]))
                groups = sub["sections"]
                if not isinstance(groups, dict):
                    sub_problems.append("%s: sections must be an object" % where)
                else:
                    if list(groups.keys()) != list(wanted_sub["groups"].keys()):
                        sub_problems.append("%s: groups must be exactly %s (found %s)" % (where, list(wanted_sub["groups"].keys()), list(groups.keys())))
                    for group, (stem, count) in wanted_sub["groups"].items():
                        items = groups.get(group)
                        gpath = "%s.%s" % (where, group)
                        if not isinstance(items, list):
                            sub_problems.append("%s: must be a list" % gpath)
                            continue
                        if len(items) != count:
                            sub_problems.append("%s: expected %d instructions, found %d" % (gpath, count, len(items)))
                        for i, item in enumerate(items):
                            _check_instruction(sub_problems, "%s[%d]" % (gpath, i), item, labels)
                        _check_id_sequence(sub_problems, gpath, [i.get("instruction_id") if isinstance(i, dict) else None for i in items], (stem,))
            problems += ["%s: %s" % (file_name, p) for p in sub_problems]

    # --- common preparedness C1 to C8
    common = data.get("common_preparedness")
    if not isinstance(common, list):
        add("common_preparedness", "must be a list")
    else:
        found_ids = [c.get("instruction_id") if isinstance(c, dict) else None for c in common]
        if found_ids != list(ex.COMMON_PREPAREDNESS_IDS):
            add("common_preparedness", "IDs must be exactly C1 to C8 in order (found %s)" % found_ids)
        for index, item in enumerate(common):
            sub_problems = []
            _check_instruction(sub_problems, "common_preparedness[%d]" % index, item, labels)
            problems += ["%s: %s" % (file_name, p) for p in sub_problems]

    # --- known conflicts, limitations, exclusions
    for key, id_key, code, keys in (
        ("known_conflicts", "conflict_id", "CF", ex.CONFLICT_KEYS),
        ("limitations", "limitation_id", "L", ex.LIMITATION_KEYS),
        ("excluded_guidance", "exclusion_id", "X", ex.EXCLUSION_KEYS),
    ):
        items = data.get(key)
        if not isinstance(items, list):
            add(key, "must be a list")
            continue
        if len(items) != expected_counts[key]:
            add(key, "expected %d entries, found %d" % (expected_counts[key], len(items)))
        for index, item in enumerate(items):
            where = "%s[%d]" % (key, index)
            sub_problems = []
            if _check_keys(sub_problems, where, item, keys):
                if not _filled(item[id_key]):
                    sub_problems.append("%s: %s must be non-empty text" % (where, id_key))
                if not _filled(item["text"]):
                    sub_problems.append("%s: text must be non-empty text" % where)
                if "reason" in item and not _filled(item["reason"]):
                    sub_problems.append("%s: reason must be non-empty text" % where)
                _check_tags(sub_problems, where, item["source_tags"], labels, allow_empty=True)
            problems += ["%s: %s" % (file_name, p) for p in sub_problems]
        sub_problems = []
        _check_id_sequence(sub_problems, key, [i.get(id_key) if isinstance(i, dict) else None for i in items], ("%s-%s" % (prefix, code),))
        problems += ["%s: %s" % (file_name, p) for p in sub_problems]

    # --- mandatory content rules
    problems += _check_mandatory_content(disaster_id, data)
    return problems


def _find_item(data: dict, item_id: str) -> Any:
    for _, item in iter_instructions(data):
        if item.get("instruction_id") == item_id:
            return item
    return None


def _check_mandatory_content(disaster_id: str, data: dict) -> List[str]:
    """Safety rules that must always hold (caveats, attribution, conflicts)."""
    file_name = disaster_id + ".json"
    problems: List[str] = []

    # FIRE-D-013: the wet-cloth caveat must exist and keep all four messages.
    if disaster_id == "fire":
        item = _find_item(data, ex.FIRE_D_013_ID)
        if item is None:
            problems.append("%s: %s is missing" % (file_name, ex.FIRE_D_013_ID))
        else:
            caveat = (item.get("caveat") or "").lower()
            if not caveat:
                problems.append("%s: %s must have its mandatory caveat" % (file_name, ex.FIRE_D_013_ID))
            for phrase in ex.FIRE_D_013_REQUIRED_PHRASES:
                if caveat and phrase not in caveat:
                    problems.append("%s: the %s caveat no longer says %r" % (file_name, ex.FIRE_D_013_ID, phrase))

    # S2*: used tag needs a source with a non-empty attribution note.
    sources = data.get("source_references") if isinstance(data.get("source_references"), list) else []
    s2_sources = [s for s in sources if isinstance(s, dict) and s.get("display_label") == "S2*"]
    s2_used = any("S2*" in (item.get("source_tags") or []) for _, item in iter_instructions(data) if isinstance(item.get("source_tags"), list))
    if s2_used:
        if not s2_sources:
            problems.append("%s: S2* items exist but there is no S2* source reference" % file_name)
        elif not _filled(s2_sources[0].get("attribution_note")):
            problems.append("%s: the S2* source has no attribution_note" % file_name)

    # Delhi Government items must keep a Delhi Government caveat.
    for path, item in iter_instructions(data):
        tags = item.get("source_tags")
        if isinstance(tags, list) and any(isinstance(t, str) and "Delhi Govt" in t for t in tags):
            if "Delhi Government" not in (item.get("caveat") or ""):
                problems.append("%s: %s: a Delhi Govt item must keep its Delhi Government caveat (%s)" % (file_name, path, item.get("instruction_id")))

    # Items tied to a preserved conflict must keep a caveat that points to it.
    for conflict_disaster, item_id in ex.CONFLICT_LINKED_ITEMS:
        if conflict_disaster == disaster_id:
            item = _find_item(data, item_id)
            if item is None:
                problems.append("%s: %s is missing" % (file_name, item_id))
            elif "known_conflicts" not in (item.get("caveat") or ""):
                problems.append("%s: %s must keep its caveat that points to known_conflicts" % (file_name, item_id))
    c6 = _find_item(data, "C6")
    if c6 is not None and "not reconciled" not in (c6.get("caveat") or ""):
        problems.append("%s: C6 must keep its food-and-water conflict caveat" % file_name)

    # Conflict texts may only name instruction IDs that exist in the file.
    known_ids = {item.get("instruction_id") for _, item in iter_instructions(data)}
    conflicts = data.get("known_conflicts") if isinstance(data.get("known_conflicts"), list) else []
    for conflict in conflicts:
        if isinstance(conflict, dict) and isinstance(conflict.get("text"), str):
            for referenced in CONFLICT_ID_PATTERN.findall(conflict["text"]):
                if referenced not in known_ids:
                    problems.append("%s: conflict %s refers to %s, which does not exist" % (file_name, conflict.get("conflict_id"), referenced))
    return problems


# ---------------------------------------------------------- cross-file validation
def validate_cross_file(all_data: AllData) -> List[str]:
    problems: List[str] = []
    valid = {d: all_data[d] for d in ex.DISASTER_ORDER if isinstance(all_data.get(d), dict)}

    # C1-C8 must be identical in all six files.
    reference = valid.get("flood", {}).get("common_preparedness")
    for disaster_id, data in valid.items():
        if data.get("common_preparedness") != reference:
            problems.append("%s.json: common_preparedness (C1-C8) differs from flood.json" % disaster_id)

    # IDs must be unique across all files (C1-C8 are shared by design).
    seen: Dict[str, str] = {}
    for disaster_id, data in valid.items():
        ids: List[str] = []
        for path, item in iter_instructions(data):
            if path != "common_preparedness" and isinstance(item.get("instruction_id"), str):
                ids.append(item["instruction_id"])
        for key, id_key in (("known_conflicts", "conflict_id"), ("limitations", "limitation_id"), ("excluded_guidance", "exclusion_id")):
            for entry in data.get(key) or []:
                if isinstance(entry, dict) and isinstance(entry.get(id_key), str):
                    ids.append(entry[id_key])
        for item_id in ids:
            if item_id in seen:
                problems.append("ID %s appears more than once (%s.json and %s.json)" % (item_id, seen[item_id], disaster_id))
            seen[item_id] = disaster_id

    # The same source must be described the same way in every file.
    first_seen: Dict[str, Tuple[str, dict]] = {}
    for disaster_id, data in valid.items():
        for source in data.get("source_references") or []:
            if not isinstance(source, dict) or not isinstance(source.get("display_label"), str):
                continue
            label = source["display_label"]
            if label not in first_seen:
                first_seen[label] = (disaster_id, source)
                continue
            other_file, other = first_seen[label]
            fields = ["source_id", "title", "organisation"]
            if label not in ex.SOURCE_URL_MAY_DIFFER:
                fields.append("url")
            if label == "S2*":
                fields.append("attribution_note")  # the mandatory S2* note must be identical everywhere
            for field in fields:
                if source.get(field) != other.get(field):
                    problems.append("source %s: '%s' differs between %s.json and %s.json" % (label, field, other_file, disaster_id))
    return problems


def validate_all(all_data: AllData) -> List[str]:
    """Run every check on all six files. An empty list means all data is valid."""
    problems: List[str] = []
    for disaster_id in all_data:
        if disaster_id not in ex.DISASTER_ORDER:
            problems.append("unexpected disaster %r: only the six approved categories are allowed" % disaster_id)
    for disaster_id in ex.DISASTER_ORDER:
        if disaster_id not in all_data:
            problems.append("%s.json is missing" % disaster_id)
        else:
            problems += validate_disaster(disaster_id, all_data[disaster_id])
    problems += validate_cross_file(all_data)
    if all(d in all_data for d in ex.DISASTER_ORDER):
        problems += limitations.check_classification({d: all_data[d] for d in ex.DISASTER_ORDER})
    return problems
