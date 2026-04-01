## Title: Add bounds checking for PA/PB indices in LTE DL modulation

### Summary
The LTE downlink modulation function uses pre-computed look-up tables (LUTs) indexed by power allocation parameters `pa` (0-7) and `pb` (0-3). While the LUT initialization functions have correct loop bounds, the usage sites in `dlsch_modulation` did not validate these indices before array access, potentially causing out-of-bounds memory access if the parameters contained unexpected values.

This change adds defensive bounds checking for `pa` and `pb` indices before accessing the QPSK and 16QAM LUT arrays in ALAMOUTI MIMO mode. The indices are clamped to valid ranges (0-7 for `pa`, 0-3 for `pb`) with a safe default of 0 if out-of-bounds.

### Changes
- `openair1/PHY/LTE_TRANSPORT/dlsch_modulation.c`: Added bounds validation for `dlsch0->pa` and `dlsch0->pb` before accessing `qam4_tm2_p2_*` and `qam16_tm2_p2_*` LUT arrays in four locations within the ALAMOUTI MIMO mode branches.

### Implementation Details
The fix uses inline ternary operators to validate indices:
```c
int pa_idx = (dlsch0->pa >= 0 && dlsch0->pa < 8) ? dlsch0->pa : 0;
int pb_idx = (dlsch0->pb >= 0 && dlsch0->pb < 4) ? dlsch0->pb : 0;
```
This ensures array accesses remain within the declared dimensions:
- `qam4_tm2_p2_0[8][256]`, `qam4_tm2_p2_1[8][256]`
- `qam4_tm2_p2_b0[8][4][256]`, `qam4_tm2_p2_b1[8][4][256]`
- `qam16_tm2_p2_0[8][256]`, `qam16_tm2_p2_1[8][256]`
- `qam16_tm2_p2_b0[8][4][256]`, `qam16_tm2_p2_b1[8][4][256]`

### Testing
- Code review confirms all array access sites now include proper bounds checking
- The fix is defensive and maintains existing behavior for valid index values
- No performance impact expected as the checks are simple integer comparisons