"""Bounded operator failure locations shared by kernel startup and service coordination, without exception messages or private execution data."""


def failure_sites(error):
    """Locate at most four internal frames per cause and four causes, excluding messages, filesystem paths, source lines and locals."""
    sites, seen = [], set()
    while error is not None and id(error) not in seen and len(sites) < 4:
        seen.add(id(error))
        frames, trace = [], error.__traceback__
        while trace is not None:
            frame = trace.tb_frame
            module = frame.f_globals.get("__name__", "")
            if module.startswith("backend."):
                frames.append(f"{module}.{frame.f_code.co_name}:{trace.tb_lineno}")
            trace = trace.tb_next
        sites.append({"type": type(error).__name__, "sites": frames[-4:]})
        error = error.__cause__ or (
            None if error.__suppress_context__ else error.__context__
        )
    return sites
