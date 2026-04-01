## Title: Fix double free vulnerability in UL retransmission allocation

### Summary
The `allocate_ul_retransmission` function in the gNB MAC UL scheduler contained a double-free vulnerability that could cause memory corruption during uplink retransmissions. The function was copying HARQ process scheduling information from `retInfo` into `sched_ctrl->sched_pusch` via structure assignment, then using a pointer to the copied data. Since `retInfo` points to memory managed by the HARQ process (which gets freed elsewhere), this created two references to the same logical allocation. When both `retInfo` and the copy in `sched_ctrl->sched_pusch` were freed, it triggered a double-free error.

The fix removes the redundant structure copy and uses the HARQ process's scheduling info pointer directly. This ensures single ownership of the allocated memory and eliminates the double-free condition while maintaining correct scheduling behavior for UL retransmissions.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_ulsch.c`: 
  - Removed the problematic structure copy `sched_ctrl->sched_pusch = *retInfo`
  - Changed `sched_pusch` pointer to directly reference `retInfo` instead of `&sched_ctrl->sched_pusch`
  - Updated RB marking logic to use `sched_pusch` consistently throughout the function
  - Applied same pattern to `pf_ul()` function for consistency

### Testing
- Ran Valgrind on gNB with UL retransmissions: confirmed no double-free errors
- Executed `nr-mac-ul-retransmission` test suite: all test cases pass
- Verified no regression in normal UL scheduling with `nr-ulsim` across various MCS levels
- Monitored memory usage during 24-hour stability test: no leaks detected