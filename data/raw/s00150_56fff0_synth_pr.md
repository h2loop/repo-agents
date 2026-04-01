## Title: Fix VCD tracer b64() to emit fixed-width 64-bit binary values

### Summary
The VCD (Value Change Dump) tracer's `b64()` function was emitting variable-length binary strings, causing protocol state machine synchronization issues with 3GPP-compliant analysis tools. When tracing 64-bit protocol state variables, the inconsistent bit width violated the VCD specification requirement for fixed-width vector dumps, leading to misinterpretation of state transitions downstream.

The function previously used a while-loop that terminated early for values with leading zeros, and had special-case handling for zero that returned a single-bit string. This patch ensures all binary values are emitted as full 64-bit vectors, maintaining consistent width across all state transitions and enabling proper protocol analysis.

### Changes
- `common/utils/T/tracer/to_vcd.c`: Modified `b64()` to always emit 64-bit binary strings by iterating from bit 63 to 0, removing the zero-value special case and variable-length output logic.

### Implementation Details
The fix replaces the conditional zero check and while-loop with a deterministic for-loop that processes all 64 bits unconditionally. This ensures VCD output format compliance and maintains protocol state machine integrity for 3GPP NAS and RRC state tracking.

### Testing
- Verified VCD output format compliance with GTKWave and other VCD parsers
- Confirmed protocol state machine traces are correctly interpreted by 3GPP analysis tools
- Validated no regression in tracer performance for high-volume logging scenarios