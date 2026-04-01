## Title: Fix null pointer dereference in nr_fill_du PRACH function

### Summary
The `nr_fill_du()` function in `nr_prach_common.c` dereferences the `prach_root_sequence_map` pointer parameter without validating it, creating a potential null pointer dereference vulnerability at line 75. This function is shared between UE and gNB PRACH processing code paths, making the issue affect both sides.

This change adds a defensive NULL pointer check at the function entry. If `prach_root_sequence_map` is NULL, the function logs an error message via `LOG_E(PHY, ...)` and returns early, preventing the crash. This maintains all existing behavior for valid inputs while improving robustness against unexpected NULL pointer scenarios.

### Changes
- `openair1/PHY/NR_TRANSPORT/nr_prach_common.c`: Added NULL validation for `prach_root_sequence_map` in `nr_fill_du()`. The check occurs before the loop at line 75 where the pointer is first dereferenced, preventing potential segmentation faults.

### Testing
- Verified the fix through code inspection: the NULL check precedes all dereferences of `prach_root_sequence_map`
- The change is minimal and defensive; no functional behavior changes when valid pointers are passed
- Both call sites (`nr_prach.c` in UE and gNB) remain compatible with this change