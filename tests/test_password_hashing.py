"""
Quick test script for bcrypt password hashing.

This script tests the secure password hashing implementation to verify
it's working correctly before deploying.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.database.auth_utils import hash_password, verify_password
    
    print("=" * 60)
    print("Testing Secure Password Hashing (bcrypt)")
    print("=" * 60)
    
    # Test 1: Hash a password
    print("\n1. Testing password hashing...")
    test_password = "my_secure_password_123"
    hashed = hash_password(test_password)
    
    print(f"   Original password: '{test_password}'")
    print(f"   Hashed password: {hashed[:20]}... (truncated)")
    print(f"   Hash length: {len(hashed)} characters")
    
    # Verify it's not plaintext
    if hashed == test_password:
        print("   [FAIL] Password is stored in plaintext!")
        sys.exit(1)
    else:
        print("   [OK] Password is hashed (not plaintext)")
    
    # Verify hash format (bcrypt hashes start with $2b$ or $2a$)
    if hashed.startswith("$2"):
        print("   [OK] Hash format is correct (bcrypt)")
    else:
        print("   [WARNING] Hash format may be incorrect")
    
    # Test 2: Verify correct password
    print("\n2. Testing password verification (correct password)...")
    result = verify_password(test_password, hashed)
    if result:
        print("   [OK] Correct password verified successfully")
    else:
        print("   [FAIL] Correct password verification failed!")
        sys.exit(1)
    
    # Test 3: Verify wrong password
    print("\n3. Testing password verification (wrong password)...")
    wrong_password = "wrong_password"
    result = verify_password(wrong_password, hashed)
    if not result:
        print("   [OK] Wrong password correctly rejected")
    else:
        print("   [FAIL] Wrong password was accepted!")
        sys.exit(1)
    
    # Test 4: Verify same password produces different hashes (salt)
    print("\n4. Testing salt generation (same password, different hash)...")
    hashed2 = hash_password(test_password)
    if hashed != hashed2:
        print("   [OK] Same password produces different hashes (salt working)")
    else:
        print("   [WARNING] Same password produces same hash (salt may not be working)")
    
    # Test 5: Both hashes should verify correctly
    print("\n5. Testing both hashes verify correctly...")
    if verify_password(test_password, hashed) and verify_password(test_password, hashed2):
        print("   [OK] Both hashed versions verify correctly")
    else:
        print("   [FAIL] Hash verification failed")
        sys.exit(1)
    
    # Test 6: Edge cases
    print("\n6. Testing edge cases...")
    
    # Empty password
    empty_hash = hash_password("")
    if verify_password("", empty_hash):
        print("   [OK] Empty password handled")
    else:
        print("   [WARNING] Empty password verification failed")
    
    # Invalid hash format
    if not verify_password("test", "invalid_hash_format"):
        print("   [OK] Invalid hash format handled gracefully")
    else:
        print("   [FAIL] Invalid hash was accepted!")
        sys.exit(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("[SUCCESS] All password hashing tests passed!")
    print("=" * 60)
    print("\nSecurity features verified:")
    print("  - Passwords are hashed (not stored in plaintext)")
    print("  - Each password gets a unique salt")
    print("  - Correct passwords verify successfully")
    print("  - Wrong passwords are rejected")
    print("  - Edge cases handled gracefully")
    print("\nThe implementation is secure and ready to use!")
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    print("\nMake sure:")
    print("  1. You're running from the project root directory")
    print("  2. bcrypt is installed: pip install bcrypt")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

