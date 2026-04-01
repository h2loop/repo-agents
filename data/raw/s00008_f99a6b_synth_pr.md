## Title: Fix SRS measurement buffer overflow and array indexing errors

### Summary
Fix buffer overflow and incorrect array indexing in `handle_nr_srs_measurements()` that caused F1AP interface message corruption between CU and DU. The function was accessing `nr_srs_bf_report.prgs[0]` instead of the proper `prgs` structure, and writing beyond allocated memory when `num_rbs` exceeded `MAX_BWP_SIZE`. This memory corruption propagated downstream, affecting F1AP message handling and causing intermittent message loss. The patch adds proper bounds checking, corrects the array access pattern, and safely limits processing to prevent buffer overruns while maintaining SRS measurement accuracy.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_ulsch.c`: 
  - Fixed incorrect array indexing: removed erroneous `[0]` subscript from `prgs[0].num_prgs`, `prgs[0].prg_list[]` accesses
  - Added `num_rbs` bounds checking against `MAX_BWP_SIZE` with warning log and clamping
  - Changed loop iteration from RB-based to PRG-based with proper PRG index bounds checking (limit 272)
  - Fixed RB marking logic to correctly map PRG-level SNR measurements to per-RB blacklist bitmap
  - Updated debug logging to reflect corrected structure access patterns

### Implementation Details
The original code incorrectly treated `prgs` as an array and used RB-indexed loops that could overflow the `ulprbbl` buffer. The fix iterates over PRGs directly, validates `num_rbs` before `memset`, and safely maps each PRG's SNR to its constituent RBs in the blacklist bitmap. This prevents memory corruption that was disrupting F1AP message flows.

### Testing
- Verified SRS measurement processing with various PRG configurations
- Confirmed no buffer overflows with `num_rbs` values exceeding `MAX_BWP_SIZE`
- Validated F1AP interface stability under sustained SRS reporting load