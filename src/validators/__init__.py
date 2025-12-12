"""
Validators Package

This package contains validation logic for user inputs.
Currently includes JavaScript-based dimension validation for real-time
input checking in the GUI.
"""

from src.validators.js_validator import DimensionValidator

__all__ = ['DimensionValidator']

