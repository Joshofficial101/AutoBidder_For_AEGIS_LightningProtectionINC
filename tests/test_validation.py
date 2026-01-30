"""
Quick test script for JavaScript dimension validator.

This script tests the JavaScript validator independently to verify
it's working before testing in the GUI.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.validators.js_validator import DimensionValidator
    
    print("=" * 60)
    print("Testing JavaScript Dimension Validator")
    print("=" * 60)
    
    # Initialize validator
    print("\n1. Initializing validator...")
    try:
        validator = DimensionValidator()
        print("   [OK] Validator initialized successfully")
    except Exception as e:
        print(f"   [ERROR] Failed to initialize: {e}")
        print("\n   Troubleshooting:")
        print("   - Make sure PyExecJS is installed: pip install PyExecJS")
        print("   - Install Node.js if needed: https://nodejs.org/")
        sys.exit(1)
    
    # Test cases
    test_cases = [
        # (input, field_type, should_be_valid, description)
        ("35", "height", True, "Simple integer"),
        ("35.5", "height", True, "Decimal number"),
        ("100.25", "height", True, "Decimal with two places"),
        ("", "height", True, "Empty string (while typing)"),
        ("35ft", "height", False, "Letters in input"),
        ("35.5.2", "height", False, "Multiple decimal points"),
        ("5,000", "area", False, "Comma separator"),
        ("-35", "height", True, "Negative number"),
        ("35-10", "height", False, "Negative sign in wrong position"),
        ("abc", "perimeter", False, "Text only"),
        ("280 linear feet", "perimeter", False, "Text with units"),
        (".", "height", True, "Just decimal point"),
        ("35@", "height", False, "Special character"),
    ]
    
    print("\n2. Running test cases...")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    for input_val, field_type, expected_valid, description in test_cases:
        if field_type == "height":
            result = validator.validate_height(input_val)
        elif field_type == "area":
            result = validator.validate_area(input_val)
        elif field_type == "perimeter":
            result = validator.validate_perimeter(input_val)
        else:
            continue
        
        is_valid = result["valid"]
        status = "[PASS]" if is_valid == expected_valid else "[FAIL]"
        
        if is_valid == expected_valid:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | Input: '{input_val}' | Expected: {'Valid' if expected_valid else 'Invalid'} | Got: {'Valid' if is_valid else 'Invalid'}")
        print(f"        Description: {description}")
        if not is_valid and result.get("error"):
            print(f"        Error: {result['error']}")
        print()
    
    # Summary
    print("-" * 60)
    print(f"\n3. Test Summary:")
    print(f"   [OK] Passed: {passed}/{len(test_cases)}")
    print(f"   [FAIL] Failed: {failed}/{len(test_cases)}")
    
    if failed == 0:
        print("\n   [SUCCESS] All tests passed! The validator is working correctly.")
        print("   You can now test it in the GUI.")
    else:
        print("\n   [WARNING] Some tests failed. Check the JavaScript validator code.")
    
    print("=" * 60)
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    print("\nMake sure you're running from the project root directory.")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

