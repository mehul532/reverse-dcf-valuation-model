"""Development shim for running ``python -m reversedcf.cli`` from repo root.

The installable package lives under ``src/reversedcf``. This shim keeps the
portfolio repo convenient to run before an editable install.
"""

from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "reversedcf"
if _SRC_PACKAGE.exists():
    __path__.append(str(_SRC_PACKAGE))

from .dcf import DCFInputs, DCFProjection, DCFValuation, run_dcf

__all__ = [
    "DCFInputs",
    "DCFProjection",
    "DCFValuation",
    "run_dcf",
]

__version__ = "0.1.0"
