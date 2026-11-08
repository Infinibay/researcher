"""Retain observations and calculate their arithmetic mean."""

def list_observations(records):
    """Return the supplied observations, preserving real zero values and order."""
    return list(records)

def mean_observations(records):
    """Return the arithmetic mean of the supplied observation values."""
    values = [record["value"] for record in list_observations(records) if record["value"]]
    return sum(values) / len(values) if values else None
