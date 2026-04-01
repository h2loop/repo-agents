## Title: Fix PTRS estimation memory access pattern in ptrs_estimate_from_slope

### Summary
Fix incorrect memory access in PTRS (Phase Tracking Reference Signal) estimation that caused phase tracking errors due to type punning between int16_t array and complex struct pointer.

The `ptrs_estimate_from_slope` function performed linear interpolation of phase errors across OFDM symbols. It incorrectly cast the input `int16_t *error_est` array to a `c16_t *` (complex struct) pointer, then accessed elements via struct fields (`.r`, `.i`). This violated strict aliasing rules and caused undefined behavior when the compiler optimized memory access patterns. The bug manifested as intermittent PTRS estimation failures, particularly on platforms with aggressive optimization.

This patch removes the unsafe cast and replaces struct-style access with explicit array indexing, treating the interleaved real/imaginary components as a flat int16_t array. This matches the actual memory layout and eliminates undefined behavior.

### Changes
- `openair1/PHY/NR_REFSIG/ptrs_nr.c`: Removed `c16_t *error` cast and struct-based memory access. Updated interpolation logic to use direct array indexing: `error_est[(start+i)*2]` for real and `error_est[((start+i)*2)+1]` for imaginary components.

### Testing
- Verified PTRS estimation accuracy with rfsimulator across multiple SNR conditions
- Confirmed no regression in downlink throughput stability
- Tested on both x86_64 and ARM64 platforms to ensure memory layout consistency