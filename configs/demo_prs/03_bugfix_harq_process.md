## Title: Fix off-by-one in HARQ process buffer indexing in MAC scheduler

### Summary
The NR gNB MAC scheduler contained an off-by-one error when indexing into the HARQ process buffer array during DLSCH retransmission scheduling. The bug manifested under high load conditions when all 16 HARQ processes were active simultaneously: the scheduler would index `harq_processes[num_harq]` instead of `harq_processes[num_harq - 1]`, reading past the end of the array. This caused occasional retransmission failures where the scheduler selected stale transport block metadata, resulting in NACK loops and reduced throughput.

The off-by-one was introduced during a previous refactor that changed HARQ process numbering from 0-based to 1-based in the scheduling request path but did not update the corresponding buffer lookup. This fix corrects the index calculation and adds an assertion to catch out-of-bounds access in debug builds.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c`: Fixed HARQ buffer index from `harq_pid` to `harq_pid - 1` in `nr_schedule_ue_spec()` retransmission path. Added `DevAssert(harq_pid > 0 && harq_pid <= MAX_HARQ_PROCESSES)` before buffer access.
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_ulsch.c`: Applied the same index correction in the UL HARQ retransmission path for consistency, though this path was not observed to trigger the bug in practice.
- `openair2/LAYER2/NR_MAC_gNB/nr_mac_gNB.h`: Added a comment clarifying that `harq_pid` values in the scheduling path are 1-based and must be decremented for array access.

### Testing
- Reproduced the bug using the `nr-dlsim` simulator with 16 UEs and full buffer traffic; confirmed retransmission failures are eliminated with the fix.
- Ran the `nr-sa-throughput-20mhz` CI pipeline with 4 UEs at full load for 120 seconds with no HARQ-related errors.
- Verified no performance regression in average DL throughput compared to the baseline.
