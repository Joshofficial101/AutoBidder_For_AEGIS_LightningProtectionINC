"""
JavaScript Validator Bridge

This module provides a Python interface to JavaScript validation functions.
Uses PyExecJS to execute JavaScript code from Python.
"""

import execjs
from pathlib import Path
from typing import Dict, Optional


class DimensionValidator:
    """
    Python wrapper for JavaScript dimension validation.
    
    This class loads the JavaScript validation module and provides
    Python methods to validate building dimensions in real-time.
    """
    
    def __init__(self):
        """Initialize the validator by loading the JavaScript module."""
        self._js_context = None
        self._load_js_validator()
    
    def _load_js_validator(self):
        """Load the JavaScript validation module."""
        try:
            # Get the path to the JavaScript file
            js_file = Path(__file__).parent / "dimension_validator.js"
            
            # Read the JavaScript code
            with open(js_file, 'r', encoding='utf-8') as f:
                js_code = f.read()
            
            # Create a JavaScript execution context
            self._js_context = execjs.compile(js_code)
            
        except FileNotFoundError:
            raise FileNotFoundError(
                f"JavaScript validator file not found: {js_file}. "
                "Please ensure dimension_validator.js exists in the validators directory."
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load JavaScript validator: {e}. "
                "Please ensure PyExecJS is installed and a JavaScript runtime is available."
            )
    
    def validate_height(self, value: str) -> Dict[str, any]:
        """
        Validate building height input.
        
        Args:
            value: Input string to validate
            
        Returns:
            Dictionary with keys:
                - valid: bool - Whether the input is valid
                - error: str - Error message if invalid, empty string if valid
                - cleaned: str - Cleaned version of the input
        """
        return self._validate_dimension(value, "height")
    
    def validate_area(self, value: str) -> Dict[str, any]:
        """
        Validate roof area input.
        
        Args:
            value: Input string to validate
            
        Returns:
            Dictionary with keys:
                - valid: bool - Whether the input is valid
                - error: str - Error message if invalid, empty string if valid
                - cleaned: str - Cleaned version of the input
        """
        return self._validate_dimension(value, "area")
    
    def validate_perimeter(self, value: str) -> Dict[str, any]:
        """
        Validate perimeter input.
        
        Args:
            value: Input string to validate
            
        Returns:
            Dictionary with keys:
                - valid: bool - Whether the input is valid
                - error: str - Error message if invalid, empty string if valid
                - cleaned: str - Cleaned version of the input
        """
        return self._validate_dimension(value, "perimeter")
    
    def _validate_dimension(self, value: str, field_name: str) -> Dict[str, any]:
        """
        Internal method to call JavaScript validation.
        
        Args:
            value: Input string to validate
            field_name: Name of the field being validated
            
        Returns:
            Dictionary with validation results
        """
        if self._js_context is None:
            # Fallback if JavaScript context failed to load
            return {
                "valid": True,  # Don't block user if validator fails
                "error": "",
                "cleaned": str(value) if value else ""
            }
        
        try:
            # Call the JavaScript validateDimension function
            result = self._js_context.call("validateDimension", value or "", field_name)
            return result
        except Exception as e:
            # If JavaScript execution fails, allow the input (don't block user)
            print(f"Warning: JavaScript validation failed: {e}")
            return {
                "valid": True,
                "error": "",
                "cleaned": str(value) if value else ""
            }

