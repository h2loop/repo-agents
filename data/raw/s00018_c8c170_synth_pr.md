## Title: Fix HARQ state machine compliance after DL HARQ list resizing

### Summary
When the gNB scheduler resizes downlink HARQ process lists during UE serving cell configuration, the HARQ process state machine transitions are not properly reset. This violates 3GPP TS 38.321 state machine requirements for HARQ entity initialization. The missing state reset can lead to undefined behavior when HARQ processes retain stale state from previous configurations.

This fix adds an explicit call to reset HARQ process states immediately after resizing the HARQ lists, ensuring all processes start in the correct initial state as mandated by the 3GPP specification.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c`: Added call to `reset_dl_harq_list()` after resizing operations in `create_dl_harq_list()` to properly initialize HARQ process states.

### Implementation Details
The `reset_dl_harq_list()` function iterates through all HARQ processes and sets them to the initial IDLE state with cleared metadata. This ensures compliance with the 3GPP state machine requirements that mandate HARQ processes be in a known initial state after entity configuration or reconfiguration.

### Testing
- Verified HARQ processes initialize in correct state after cell configuration changes
- Confirmed no regression in downlink throughput with multiple UEs
- Validated against 3GPP TS 38.321 state machine requirements