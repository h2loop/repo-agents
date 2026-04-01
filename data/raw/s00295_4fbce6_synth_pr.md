## Title: Replace magic number with named constant in CRC16 implementation

### Summary
The `crc16()` function used the literal value `16` as a bit shift offset to align 16-bit CRC results within a 32-bit register. This magic number lacked context, making the code difficult to understand and maintain.

This change introduces the named constant `CRC_SHIFT_OFFSET_16BIT` to explicitly document the purpose of this shift operation. Using a symbolic constant improves code readability and reduces the risk of future maintenance errors if this offset needs to be adjusted.

### Changes
- `openair1/PHY/CODING/crc_byte.c`: 
  - Added `CRC_SHIFT_OFFSET_16BIT` macro definition (value: 16) near other polynomial constants
  - Replaced two instances of the magic number `16` with the new constant in the `crc16()` function

### Implementation Details
The constant is defined in the header section alongside other CRC polynomial constants for consistency and discoverability. Both shift operations in the main processing loop and residual bit handling now use the named constant, ensuring uniform behavior throughout the function.

### Testing
- Verified successful compilation with the changes
- No functional impact expected; this is a pure code clarity improvement

---