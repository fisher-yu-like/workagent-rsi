"""Syntax validation for file-reading coordinates,not task acceptance."""

import re
from .assessment_contracts import Location


def validate_location(location, domain, *, fact=False):
    """Configuration syntax only; object existence is an artifact observation."""
    loc = Location.model_validate(location)
    groups = {
        "excel": ["sheet", "cell"],
        "word": ["paragraph", "heading", "table"],
        "powerpoint": ["slide", "object_id"],
    }
    for other, fields in groups.items():
        if other != domain and any(getattr(loc, name) is not None for name in fields):
            raise ValueError("location belongs to a different artifact domain")
    if loc.cell is not None:
        if not loc.sheet or not re.fullmatch(
            r"\$?[A-Za-z]{1,3}\$?[1-9][0-9]*(?::\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)?",
            loc.cell,
        ):
            raise ValueError(
                "cell/range requires explicit sheet and valid Excel coordinates"
            )
        from openpyxl.utils.cell import range_boundaries

        a, b, c, d = range_boundaries(loc.cell)
        if a > c or b > d or c > 16384 or d > 1048576:
            raise ValueError("Excel range is reversed or outside worksheet limits")
    if (loc.row is None) != (loc.column is None):
        raise ValueError("table scope needs both row and column")
    if loc.row is not None and (
        (domain == "word" and loc.table is None)
        or (domain == "powerpoint" and (loc.slide is None or loc.object_id is None))
        or domain == "excel"
    ):
        raise ValueError("table cell needs an explicit table/object location")
    if loc.object_id is not None and loc.slide is None:
        raise ValueError("object scope requires slide")
    if loc.group_path is not None and (domain != "powerpoint" or loc.slide is None):
        raise ValueError("group path requires an explicit PowerPoint slide")
    if (
        domain == "word"
        and loc.table is not None
        and (loc.paragraph is not None or loc.heading is not None)
    ):
        raise ValueError("paragraph/heading and table selectors are conflicting")
    if fact:
        valid = (
            domain == "excel"
            and loc.sheet
            and loc.cell
            and ":" not in loc.cell
            or domain == "word"
            and (loc.paragraph or loc.table and loc.row and loc.column)
            or domain == "powerpoint"
            and loc.slide
            and loc.object_id is not None
        )
        if not valid:
            raise ValueError(
                "fact check needs an exact cell/paragraph/table/object location"
            )
    return loc
