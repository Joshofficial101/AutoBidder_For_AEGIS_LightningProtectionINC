# WARNING: This file is for demonstration purposes only. 
# It provides dummy functions to satisfy imports without using bcrypt.

def hash_password(password: str) -> str:
    """DUMMY: Returns the password as the 'hash'."""
    # Insecurely returns the password itself for demo purposes
    return password

def verify_password(password: str, stored_password: str) -> bool:
    """DUMMY: Verifies a plaintext password against a stored plaintext password."""
    # Insecurely checks if the passwords are equal
    return password == stored_password