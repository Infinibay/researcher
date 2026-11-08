"""Calculate a synthetic self-reported proportion; no causal comparison is encoded."""
PARTICIPANTS = 40
REPORTED_IMPROVEMENT = 28

def reported_improvement_fraction():
    """Return the observed fraction without attributing improvement to the program."""
    return REPORTED_IMPROVEMENT / PARTICIPANTS
