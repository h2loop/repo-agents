## Title: Add error propagation to quantization functions in LDPC testbench

### Summary
The quantization functions (`quantize4bit`, `quantize8bit`, and `quantize`) in the LDPC testbench silently failed when given invalid inputs (NaN, Inf, or zero denominator), causing undefined behavior in the floor() operation and potential data corruption. This change adds input validation and error propagation so callers can detect and handle quantization failures appropriately.

### Changes
- `openair1/PHY/CODING/TESTBENCH/coding_unitary_defs.h`: Added validation in `quantize()` to check for NaN, Inf, and D=0.0 before division; returns -128 on error
- `openair1/PHY/CODING/TESTBENCH/ldpctest.c`: 
  - Added same validation to `quantize4bit()` and `quantize8bit()`
  - Added `quantization_errors` counter to `one_measurement_t` struct
  - Added error checking after `quantize()` calls in `test_ldpc()`
  - Prints quantization error count in final results

### Implementation Details
Functions return -128 (outside normal quantization range) as an error indicator. The test loop detects this value, increments the error counter, and prints diagnostic messages. This prevents silent failures and provides visibility into quantization issues during LDPC decoder testing.