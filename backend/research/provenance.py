"""Bound structural provenance disclosure while retaining exact normalized-text locators."""

import json


def provenance_summary(provenance):
    """Keep interpretation/limits visible; recover large unit lists via source structure pages."""
    summary = {key: value for key, value in provenance.items() if key != "units"}
    if "units" in provenance:
        summary["unit_count"] = len(provenance["units"])
        summary["structure_paged"] = True
    return summary


def structure_page(provenance, *, after_index, limit):
    """Return at most 100 units and 12000 encoded unit bytes with a continuation index."""
    if (
        type(after_index) is not int
        or after_index < 0
        or type(limit) is not int
        or not 1 <= limit <= 100
    ):
        raise ValueError("Structure page requires nonnegative index and limit 1–100")
    units = provenance.get("units", [])
    selected, size = [], 0
    for unit in units[after_index : after_index + limit]:
        encoded = len(json.dumps(unit, ensure_ascii=False).encode("utf-8")) + 2
        if size + encoded > 12000:
            break
        selected.append(unit)
        size += encoded
    end = after_index + len(selected)
    return {
        "units": selected,
        "total_units": len(units),
        "after_index": after_index,
        "next_index": end if end < len(units) else None,
    }


def intersecting_units(provenance, start, end):
    """Link an exact normalized excerpt to compact unit indices rather than duplicating locators."""
    return [
        unit["index"]
        for unit in provenance.get("units", [])
        if unit["start_offset"] < end and unit["end_offset"] > start
    ]
