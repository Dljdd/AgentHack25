# Compatibility shim for Python < 3.12 to support typing.override
# This file is auto-imported by Python if present on sys.path.
# For CLI tools invoked from this project dir, this backfills typing.override
# using typing_extensions.override when available.

import typing

try:
    from typing_extensions import override as _override  # type: ignore
    if not hasattr(typing, "override"):
        # Attach attribute for libraries that import from typing
        typing.override = _override  # type: ignore[attr-defined]
except Exception:
    # If typing_extensions not installed, do nothing; installing it will fix.
    pass
