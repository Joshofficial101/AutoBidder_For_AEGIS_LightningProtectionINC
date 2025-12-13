/**
 * Dimension Validator - JavaScript Module
 * 
 * Validates building dimension inputs (height, area, perimeter) in real-time.
 * This module is called from Python via PyExecJS to provide validation logic.
 * 
 * Rules:
 * - Only digits, decimal point (.), and optional negative sign (-) allowed
 * - No letters, special symbols (except . and -)
 * - Decimal point can only appear once
 * - Negative sign only at start
 * - Empty string is valid (user is still typing)
 */

/**
 * Validates a dimension input string
 * @param {string} input - The input string to validate
 * @param {string} fieldName - The field name ("height", "area", "perimeter")
 * @returns {Object} Validation result with {valid: boolean, error: string, cleaned: string}
 */
function validateDimension(input, fieldName) {
    // Empty string is valid (user is still typing)
    if (input === "" || input === null || input === undefined) {
        return {
            valid: true,
            error: "",
            cleaned: ""
        };
    }
    
    // Convert to string and trim whitespace (compatible with older JS engines)
    var str = String(input);
    // Manual trim for compatibility with older JavaScript engines
    str = str.replace(/^\s+|\s+$/g, '');
    
    // Check for invalid characters (anything that's not a digit, decimal point, or negative sign)
    var invalidCharPattern = /[^0-9.\-]/;
    var invalidMatch = str.match(invalidCharPattern);
    
    if (invalidMatch) {
        var invalidChar = invalidMatch[0];
        return {
            valid: false,
            error: "Invalid character: '" + invalidChar + "'. Only numbers and decimal point allowed.",
            cleaned: str.replace(/[^0-9.\-]/g, '')
        };
    }
    
    // Check for multiple decimal points
    var decimalCount = (str.match(/\./g) || []).length;
    if (decimalCount > 1) {
        return {
            valid: false,
            error: "Multiple decimal points not allowed.",
            cleaned: str.split('.').slice(0, 2).join('.')
        };
    }
    
    // Check for negative sign in wrong position
    var negativeIndex = str.indexOf('-');
    if (negativeIndex !== -1 && negativeIndex !== 0) {
        return {
            valid: false,
            error: "Negative sign (-) must be at the beginning.",
            cleaned: str.replace(/-/g, '')
        };
    }
    
    // Check for multiple negative signs
    var negativeCount = (str.match(/-/g) || []).length;
    if (negativeCount > 1) {
        return {
            valid: false,
            error: "Multiple negative signs not allowed.",
            cleaned: str.replace(/-/g, '').replace(/^/, '-')
        };
    }
    
    // Check for decimal point at start or end (edge cases)
    if (str === '.' || str === '-.' || str === '-') {
        return {
            valid: true,  // Allow while typing (user might be entering "0.5")
            error: "",
            cleaned: str
        };
    }
    
    // If we get here, the input is valid
    return {
        valid: true,
        error: "",
        cleaned: str
    };
}

// Export for use with PyExecJS
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { validateDimension: validateDimension };
}

