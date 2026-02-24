# Testing Real-Time Input Validation

This guide explains how to test the JavaScript-based real-time validation feature for building dimension fields.

## Prerequisites

1. **Install the new dependency:**
   ```bash
   pip install PyExecJS
   ```
   
   Or reinstall all dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. **JavaScript Runtime:**
   - PyExecJS requires a JavaScript runtime
   - On Windows, it will try to use Node.js if installed, or fall back to other engines
   - If you get errors about missing JavaScript runtime, install Node.js from https://nodejs.org/

## Running the Application

1. **Start the GUI:**
   ```bash
   run_desktop.cmd
   ```
   
   Or use the batch file:
   ```bash
   run_desktop.cmd
   ```

2. **Login:**
   - Sign in with any username/password (or create an account)
   - You'll be taken to the main bidding window

## Testing the Validation

### Test 1: Valid Inputs

1. **Building Height Field:**
   - Type: `35`
   - Expected: No error, normal border
   - Type: `35.5`
   - Expected: No error, normal border
   - Type: `100.25`
   - Expected: No error, normal border

2. **Roof Area Field:**
   - Type: `5000`
   - Expected: No error
   - Type: `5000.5`
   - Expected: No error

3. **Perimeter Field:**
   - Type: `280`
   - Expected: No error
   - Type: `840.25`
   - Expected: No error

### Test 2: Invalid Characters

1. **Letters in Height:**
   - Type: `35ft`
   - Expected: 
     - Red border appears
     - Error message: "Invalid character: 'f'. Only numbers and decimal point allowed."
     - Error text appears below the field

2. **Special Symbols:**
   - Type: `35@` in any field
   - Expected: Red border + error about invalid character '@'

3. **Multiple Decimal Points:**
   - Type: `35.5.2` in any field
   - Expected: Red border + error: "Multiple decimal points not allowed."

4. **Commas (common mistake):**
   - Type: `5,000` in area field
   - Expected: Red border + error about invalid character ','

5. **Text Units:**
   - Type: `280 linear feet` in perimeter
   - Expected: Red border + error about invalid characters

### Test 3: Edge Cases

1. **Empty Field:**
   - Clear a field completely
   - Expected: No error (empty is valid while typing)

2. **Negative Numbers:**
   - Type: `-35` in height
   - Expected: Valid (negative sign at start is allowed)
   - Type: `35-10` in height
   - Expected: Invalid - error about negative sign position

3. **Decimal Point Only:**
   - Type: `.` in a field
   - Expected: Valid (user might be typing "0.5")

### Test 4: Real-Time Feedback

1. **Start with Invalid:**
   - Type: `abc` in height field
   - Expected: Immediate red border + error

2. **Fix the Input:**
   - Delete and type: `35`
   - Expected: Red border disappears, error clears immediately

3. **Partial Typing:**
   - Type: `3` → No error
   - Type: `35` → No error
   - Type: `35f` → Error appears
   - Delete `f` → Error clears

### Test 5: Calculate Bid Button State

1. **With Validation Errors:**
   - Enter invalid data in any dimension field (e.g., `35ft`)
   - Expected: "Calculate Bid" button should be **disabled** (grayed out)

2. **Fix All Errors:**
   - Fix all invalid inputs
   - Load Excel pricing file
   - Expected: "Calculate Bid" button should be **enabled**

3. **Without Pricing:**
   - All fields valid, but no Excel loaded
   - Expected: "Calculate Bid" button should be **disabled**

### Test 6: PDF Parsing Integration

1. **Parse a PDF:**
   - Click "Parse PDF" button
   - Select a PDF with dimensions
   - Expected: Fields auto-fill with extracted values
   - Expected: Validation runs automatically on auto-filled values
   - Expected: If extracted values are valid numbers, no errors appear

## What to Look For

### Visual Indicators:
- ✅ **Valid Input:** Normal border, no error text
- ❌ **Invalid Input:** Red border, error text below field
- 🔒 **Button State:** Calculate Bid button disabled when errors exist

### Console Output:
- Check the terminal/console for any JavaScript execution errors
- If you see "Warning: Could not initialize dimension validator", the JavaScript runtime might not be available

## Troubleshooting

### Issue: "No JavaScript runtime found"
**Solution:** Install Node.js from https://nodejs.org/ (any recent version)

### Issue: Validation not working
**Check:**
1. Is PyExecJS installed? `pip list | findstr PyExecJS`
2. Check console for error messages
3. Validation will gracefully fall back if JavaScript fails (won't block user)

### Issue: Button stays disabled
**Check:**
1. Are all dimension fields valid? (no red borders)
2. Is Excel pricing loaded? (click "Load Excel" first)
3. Check `validation_errors` state in console if needed

## Expected Behavior Summary

| Input | Height | Area | Perimeter | Result |
|-------|--------|------|-----------|--------|
| `35` | ✅ | ✅ | ✅ | Valid |
| `35.5` | ✅ | ✅ | ✅ | Valid |
| `35ft` | ❌ | ❌ | ❌ | Invalid - letters |
| `35.5.2` | ❌ | ❌ | ❌ | Invalid - multiple decimals |
| `5,000` | ❌ | ❌ | ❌ | Invalid - comma |
| `-35` | ✅ | ✅ | ✅ | Valid - negative |
| `35-10` | ❌ | ❌ | ❌ | Invalid - negative position |
| `` (empty) | ✅ | ✅ | ✅ | Valid - while typing |

## Success Criteria

The validation is working correctly if:
1. ✅ Invalid characters show red border immediately
2. ✅ Error messages appear below invalid fields
3. ✅ Errors clear when input becomes valid
4. ✅ Calculate Bid button disables when errors exist
5. ✅ No console errors about JavaScript execution
6. ✅ Validation works for all three fields (height, area, perimeter)

