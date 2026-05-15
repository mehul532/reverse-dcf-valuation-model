"""Reverse DCF valuation toolkit.

This package is intended for educational valuation analysis. It does not
provide investment advice or predictions about future security prices.
"""

from reversedcf.dcf import DCFInputs, DCFProjection, DCFValuation, run_dcf

__all__ = [
    "DCFInputs",
    "DCFProjection",
    "DCFValuation",
    "run_dcf",
]

__version__ = "0.1.0"
