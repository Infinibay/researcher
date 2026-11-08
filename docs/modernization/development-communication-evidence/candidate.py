"""List observations in input order and export them as spreadsheet CSV text."""

import csv
import io


def list_observations(records):
    """Return observations in their supplied order without inferring their schema."""
    return list(records)


def export_observations(records):
    """Return id/value CSV text in input order, rejecting missing required keys."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["id", "value"])
    for record in list_observations(records):
        if "id" not in record or "value" not in record:
            raise ValueError("Each observation must contain id and value")
        writer.writerow([record["id"], record["value"]])
    return output.getvalue()
