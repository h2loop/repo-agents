## Title: Fix HARQ process handling in SLSCH procedures for sidelink

### Summary
The sidelink SLSCH procedures contain incorrect HARQ process management that causes retransmission failures and wrong redundancy version (RV) selection. The original implementation unconditionally sets `harq_to_be_cleared=true` without proper HARQ state tracking, leading to incorrect behavior for both new transmissions and retransmissions.

This fix implements proper HARQ process management for sidelink shared channel decoding. It adds correct HARQ state initialization for new transmissions (when NDI=1), implements the 3GPP-specified RV sequence [0,2,3,1] based on HARQ round number, and properly updates HARQ process state after decoding attempts. The HARQ round increments after successful decoding, and the process resets after maximum retransmissions (4 rounds) to prevent infinite retransmission loops.

### Changes
- `openair1/SCHED_NR_UE/phy_procedures_nr_ue_sl.c`: Replaces simplistic HARQ clearing logic with proper HARQ state management. Adds initialization for new transmissions, RV index calculation based on HARQ round, and state updates after decoding.

### Implementation Details
The fix uses `ue->sl_harq_processes[harq_pid]` for proper HARQ process indexing. For new transmissions (NDI=1), it resets the HARQ round to 0, marks the process as ACTIVE, and stores the PDU configuration. The RV index is automatically determined from the HARQ round using the sequence defined in 3GPP TS 38.214. After decoding, the HARQ round increments on success and the process resets after 4 rounds, while decoding failures keep the process ACTIVE for retransmission.