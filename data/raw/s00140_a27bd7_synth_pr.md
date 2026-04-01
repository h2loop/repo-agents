## Title: Clear stale HARQ state to prevent DMRS configuration corruption

### Summary
Fix stale protocol state accumulation in NR MAC gNB HARQ processes that could lead to incorrect DMRS (Demodulation Reference Signal) configuration in subsequent transmissions. When DL or UL HARQ processes were aborted or completed, the `sched_pdsch` and `sched_pusch` structures retained previous transmission parameters. This caused potential misconfiguration of DMRS masks and other protocol parameters when HARQ processes were reused for retransmissions or new transmissions.

The fix ensures HARQ state is fully reset at key state transitions by clearing the scheduling structures, preventing any residual data from affecting future transmissions.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c`: Clear `sched_pdsch` structure in `abort_nr_dl_harq()` when DL HARQ processes are aborted due to errors or excessive retransmissions.
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_uci.c`: Clear `sched_pdsch` structure when DL HARQ is successfully completed (ACK received), ensuring clean state for next transmission.
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_ulsch.c`: Clear `sched_pusch` structure in `abort_nr_ul_harq()` and upon successful UL HARQ completion, preventing stale UL scheduling parameters from persisting.

### Implementation Details
The solution uses `memset()` to zero out the entire `sched_pdsch` and `sched_pusch` structures (each ~200-300 bytes) at HARQ state transition points. This is a robust approach that ensures all fields, including DMRS configuration derived from `fill_dmrs_mask()` and other protocol parameters, are reset. The clearing occurs both on successful completion (ACK) and abortion (error/timeout) paths, covering all HARQ process reuse scenarios.

### Testing
- Verified HARQ process reuse with multiple consecutive transmissions
- Confirmed no regression in DL/UL throughput in basic functionality tests
- Validated that DMRS configuration is correctly recomputed for each new transmission