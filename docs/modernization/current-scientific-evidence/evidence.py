"""Transcribed abstract counts retain patient denominators; no causal comparison is encoded."""
OUTCOMES = {"open_surgery": {"patients": 350, "successes": 273}, "percutaneous": {"patients": 350, "successes": 289}}
def success_rate(group):
    """Calculate a recorded proportion without asserting randomized assignment or clinical suitability."""
    return group["successes"] / group["patients"]
