## Title: Fix out-of-bounds memory read in small block encoder

### Summary
The `encodeSmallBlock()` function reads beyond the bounds of the `nrSmallBlockBasis` array when the `len` parameter exceeds 11, causing undefined behavior and potential crashes. The statically defined `nrSmallBlockBasis` array contains only 11 elements (indices 0-10), but the function iterates from 0 to `len-1` without validating the input parameter. Call sites in the PHY layer (e.g., `pucch_nr.c`) pass the number of UCI bits directly, which can exceed 11 in certain configurations, leading to uninitialized memory access.

This patch adds an explicit bounds check to clamp the length parameter to the maximum supported value of 11, ensuring safe array access.

### Changes
- `openair1/PHY/CODING/nrSmallBlock/encodeSmallBlock.c`: Added input validation to constrain `len` to ≤ 11 before the encoding loop.

### Implementation Details
The fix inserts a bounds check at the function entry point. If `len > 11`, it is clamped to 11, preventing the subsequent XOR loop from accessing `nrSmallBlockBasis[i]` beyond the array's allocated memory. This preserves the existing encoding behavior for valid inputs while eliminating the memory safety violation.

### Testing
- Code inspection confirms the `nrSmallBlockBasis` array size is 11, matching the clamp value.
- The change prevents undefined behavior for all possible input lengths while maintaining correct encoding for valid small block lengths (≤ 11 bits).