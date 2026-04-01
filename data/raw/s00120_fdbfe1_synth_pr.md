## Title: Fix incorrect type cast in sqrt_float causing precision loss

### Summary
The `sqrt_float` helper function in the LTE UE transport layer was performing unnecessary and incorrect type conversions that caused precision loss. The implementation cast the input `float` to `double`, called `sqrt()` (double-precision), then cast back to `float`. This introduced both performance overhead and potential data corruption due to the double rounding.

This patch replaces the inefficient cast pattern with the native single-precision `sqrtf()` function, eliminating the double-to-float conversion entirely. This ensures correct single-precision math throughout the linear preprocessing pipeline and removes a source of numerical instability in MMSE whitening filter calculations.

### Changes
- `openair1/PHY/LTE_UE_TRANSPORT/linear_preprocessing_rec.c`: Simplified `sqrt_float()` to use `sqrtf(x)` directly instead of `(float)(sqrt((double)(x)))`

### Implementation Details
The function signature remains unchanged: `float sqrt_float(float x, float sqrt_x)`. The implementation now uses the C standard library's `sqrtf()` which operates entirely in single-precision, avoiding the problematic double-precision intermediate representation. This is particularly important for the linear preprocessing calculations where numerical accuracy directly impacts channel estimation quality.

### Testing
- Verified compilation with `-Wdouble-promotion` flags to ensure no unintended double conversions remain
- Ran unit tests for MMSE whitening filter to confirm numerical stability
- Validated with `lte-uesoftmodem` in loopback mode showing consistent throughput before and after change