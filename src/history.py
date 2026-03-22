"""
history.py — Snapshot comparison utilities for the KEK media archive.

The archive stores one JSON snapshot per day (committed via the GitHub Actions
"clock" workflow).  This module lets you compare any two snapshots of
``media.json`` / ``shareholders.json`` to answer questions like:

  * Which entries were added / removed between date A and date B?
  * Which ``controlDate`` values changed (i.e. whose ownership data was
    updated)?
  * What concrete field-level differences exist for a given entity?

Addresses the requirement:
  "Versioning/History: The ability to track changes over time
   (who owned what and when)."
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def load_snapshot(path: Path) -> Dict[str, dict]:
    """
    Load a ``media.json`` or ``shareholders.json`` file and return a mapping
    of ``squuid`` → raw dict.

    :param path: Absolute path to the JSON list file.
    :returns: ``{squuid: entry_dict}``
    """
    entries = json.loads(path.read_text(encoding="utf-8"))
    return {e["squuid"]: e for e in entries}


def compare_snapshots(
    old: Dict[str, dict],
    new: Dict[str, dict],
) -> "SnapshotDiff":
    """
    Compare two snapshots (as returned by :func:`load_snapshot`) and return a
    :class:`SnapshotDiff` describing what changed.

    :param old: Mapping produced from the *earlier* snapshot.
    :param new: Mapping produced from the *later* snapshot.
    :returns: :class:`SnapshotDiff`
    """
    old_keys = set(old)
    new_keys = set(new)

    added = {k: new[k] for k in new_keys - old_keys}
    removed = {k: old[k] for k in old_keys - new_keys}

    changed: Dict[str, List[Tuple[str, object, object]]] = {}
    for k in old_keys & new_keys:
        diffs = _diff_dicts(old[k], new[k])
        if diffs:
            changed[k] = diffs

    return SnapshotDiff(added=added, removed=removed, changed=changed)


# ---------------------------------------------------------------------------
# SnapshotDiff
# ---------------------------------------------------------------------------

class SnapshotDiff:
    """
    Result of comparing two snapshots.

    Attributes
    ----------
    added : dict[squuid, entry]
        Entities present in the *new* snapshot but not the *old* one.
    removed : dict[squuid, entry]
        Entities present in the *old* snapshot but not the *new* one.
    changed : dict[squuid, list[tuple[field, old_value, new_value]]]
        Entities that exist in both snapshots but have at least one differing
        top-level field.  Each inner tuple is ``(field_name, old_value,
        new_value)``.
    """

    def __init__(
        self,
        added: Dict[str, dict],
        removed: Dict[str, dict],
        changed: Dict[str, List[Tuple[str, object, object]]],
    ):
        self.added = added
        self.removed = removed
        self.changed = changed

    # ------------------------------------------------------------------
    # Convenience queries
    # ------------------------------------------------------------------

    def control_date_changes(self) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """
        Return only the ``controlDate`` changes – i.e. entities whose ownership
        data was updated between the two snapshots.

        :returns: ``{squuid: (old_controlDate, new_controlDate)}``
        """
        result = {}
        for squuid, diffs in self.changed.items():
            for field, old_val, new_val in diffs:
                if field == "controlDate":
                    result[squuid] = (old_val, new_val)
        return result

    def summary(self) -> str:
        """Return a short human-readable summary of the diff."""
        lines = [
            f"Added   : {len(self.added)} entities",
            f"Removed : {len(self.removed)} entities",
            f"Changed : {len(self.changed)} entities",
            f"  of which controlDate changed: {len(self.control_date_changes())}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"SnapshotDiff(added={len(self.added)}, "
            f"removed={len(self.removed)}, "
            f"changed={len(self.changed)})"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _diff_dicts(
    old: dict,
    new: dict,
) -> List[Tuple[str, object, object]]:
    """
    Return a list of ``(field, old_value, new_value)`` for every top-level key
    that differs between *old* and *new*.
    """
    diffs = []
    all_keys = set(old) | set(new)
    for key in sorted(all_keys):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            diffs.append((key, old_val, new_val))
    return diffs
