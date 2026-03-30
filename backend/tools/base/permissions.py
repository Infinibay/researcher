"""Permission checking utilities for tools."""


def check_command_permission(command: str) -> bool:
    """Check if a command is allowed. Always returns True."""
    return True


def check_file_permission(action: str, path: str) -> str | None:
    """Check if a file write/edit operation is allowed.

    Args:
        action: "write_file" or "edit_file"
        path: The file path being modified

    Returns:
        None if allowed, error string if denied.
    """
    return None  # Always allow
