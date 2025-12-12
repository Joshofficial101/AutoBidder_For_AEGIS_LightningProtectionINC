"""
Password Hashing Utilities

This module provides secure password hashing and verification using bcrypt.
Passwords are hashed with a salt and cannot be reversed to plaintext.
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with automatic salt generation.
    
    Args:
        password: Plaintext password to hash
        
    Returns:
        Hashed password string (includes salt) that can be safely stored
        
    Example:
        >>> hashed = hash_password("my_password")
        >>> len(hashed) > 50  # bcrypt hashes are 60 characters
        True
    """
    # Convert password to bytes (bcrypt requires bytes)
    password_bytes = password.encode('utf-8')
    
    # Generate salt and hash password (bcrypt.gensalt() generates a random salt)
    # rounds=12 is a good balance between security and performance
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_password(password: str, stored_password: str) -> bool:
    """
    Verify a password against a stored hash.
    
    Args:
        password: Plaintext password to verify
        stored_password: Previously hashed password from database
        
    Returns:
        True if password matches, False otherwise
        
    Example:
        >>> hashed = hash_password("my_password")
        >>> verify_password("my_password", hashed)
        True
        >>> verify_password("wrong_password", hashed)
        False
    """
    try:
        # Convert both to bytes
        password_bytes = password.encode('utf-8')
        stored_bytes = stored_password.encode('utf-8')
        
        # bcrypt.checkpw() securely compares the password with the hash
        # It handles the salt extraction and comparison automatically
        return bcrypt.checkpw(password_bytes, stored_bytes)
    except (ValueError, TypeError, AttributeError):
        # Handle edge cases: invalid hash format, None values, etc.
        return False