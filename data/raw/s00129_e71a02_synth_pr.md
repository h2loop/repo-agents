## Title: Fix incorrect array sizing in NR PSS time search for sidelink mode

### Summary
The `pss_search_time_nr` function in the NR UE PSS search module incorrectly allocates a fixed-size array for correlation averaging, causing out-of-bounds memory access in sidelink mode. The `avg` array was hardcoded to `NUMBER_PSS_SEQUENCE` elements, but when sidelink mode is active (`sl_mode != 0`), the downstream logic iterates over `NUMBER_PSS_SEQUENCE_SL` elements. This mismatch leads to undefined behavior and potential crashes during PSS detection in sidelink configurations.

The fix dynamically sizes the `avg` array based on the current operating mode, matching the existing pattern used for the `pssTime` array sizing in the same function. This ensures proper memory bounds regardless of mode.

### Changes
- `openair1/PHY/NR_UE_TRANSPORT/pss_nr.c`: 
  - Calculate `max_avg_size` based on `sl_mode` (similar to `max_size`)
  - Replace fixed-size `avg[NUMBER_PSS_SEQUENCE]` with variable-length `avg[max_avg_size]`
  - Replace static array initialization with explicit loop initialization to zero

### Implementation Details
The implementation follows the established pattern in the function where `max_size` is conditionally set based on `get_softmodem_params()->sl_mode`. The variable-length array is stack-allocated and explicitly initialized element-by-element to avoid compiler limitations on VLA initialization. This maintains consistency with the existing codebase style while fixing the bounds violation.

### Testing
- Verified PSS detection works correctly in both normal mode and sidelink mode
- Confirmed no regression in cell search performance for standard NR operation
- Validated memory access stays within bounds under all `sl_mode` configurations