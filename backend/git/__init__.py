"""Git execution modules without eager database, settings or web-service imports.

The web API explicitly imports backend.git.services to construct its shared
repository/branch/publication readers. Native capsules and recovery processes
can import their own modules in isolated standard-library Python.
"""
