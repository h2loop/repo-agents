## Title: Fix use-after-free vulnerability in PRACH subframe detection

### Summary
The `is_prach_subframe()` function in the LTE PRACH transport layer contained a use-after-free vulnerability. The function accessed `frame_parms` and its nested configuration structures multiple times throughout execution, creating a time window where if the `frame_parms` memory was freed by another thread or calling context, subsequent accesses would operate on stale memory. This could lead to crashes, data corruption, or unpredictable PRACH scheduling behavior.

The fix implements a defensive copying pattern: all necessary data from `frame_parms` is copied to local variables at function entry before any processing occurs. This ensures the function operates on a consistent snapshot of configuration data, eliminating the use-after-free risk regardless of when `frame_parms` memory is released.

### Changes
- `openair1/PHY/LTE_TRANSPORT/prach_common.c`: Refactored `is_prach_subframe()` to copy `tdd_config`, `frame_type`, `prach_ConfigIndex`, and the `prach_emtc_config_common` arrays to local variables before processing. All subsequent logic uses these local copies.

### Implementation Details
The function now performs a single read pass on `frame_parms` at the beginning, copying:
- Scalar values: `tdd_config`, `frame_type`, `prach_ConfigIndex`
- Array data: `prach_CElevel_enable[4]` and `prach_ConfigIndex[4]` from eMTC config

The core logic remains unchanged; only the data access pattern is modified to use local variables. This approach maintains thread safety without requiring locks and has minimal performance impact since the copied data is small and stack-allocated.