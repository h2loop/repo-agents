## Title: Fix variable reuse bug in log2_approx64 function

### Summary
The `log2_approx64()` function contained a copy-paste error where the same variable `l2` was reused to store both the leading zero count from `simde_x_clz64()` and the final logarithm approximation result. This reduced code clarity and diverged from the pattern used in the 32-bit `log2_approx()` counterpart.

This fix introduces a separate `leading_zeros` variable to hold the CLZ result, then uses it to compute the final `l2` value. The separation makes the two-step algorithm explicit: first count leading zeros, then derive the log2 approximation. No functional behavior is changed.

### Changes
- `openair1/PHY/TOOLS/log2_approx.c`: Refactored `log2_approx64()` to use distinct variables for the CLZ result (`leading_zeros`) and final approximation (`l2`), improving readability and maintainability.

### Testing
- Verified the approximation logic produces identical results
- Code now follows the same clear pattern as the 32-bit version