## Title: Fix invalid array access bounds in UE release cleanup

### Summary
The UE release cleanup logic in `release_UE_in_freeList()` contained insufficient bounds checking when cleaning up ULSCH and DLSCH entries for released UEs. The `find_ulsch()` and `find_dlsch()` helper functions could return indices that exceed the respective array limits (`NUMBER_OF_ULSCH_MAX` and `NUMBER_OF_DLSCH_MAX`), but the code only validated the lower bound (`id >= 0`) before dereferencing the arrays. This could lead to out-of-bounds memory access and potential heap corruption during UE context teardown, especially under high load or error conditions where the lookup functions return sentinel values at or beyond the array boundaries.

The fix adds explicit upper bound checks to ensure array indices are valid before accessing `eNB_PHY->ulsch[id]` and `eNB_PHY->dlsch[id][0]`.

### Changes
- `openair2/RRC/LTE/rrc_eNB.c`: Added upper bound validation (`id < NUMBER_OF_ULSCH_MAX` and `id < NUMBER_OF_DLSCH_MAX`) in `release_UE_in_freeList()` before calling `clean_eNb_ulsch()` and `clean_eNb_dlsch()`.

### Implementation Details
The bounds checks are added immediately after the `find_ulsch()` and `find_dlsch()` calls, following the existing lower bound check pattern. This ensures defensive programming without changing the cleanup logic flow. The constants `NUMBER_OF_ULSCH_MAX` and `NUMBER_OF_DLSCH_MAX` are already defined in the codebase and represent the statically allocated array sizes for these structures.