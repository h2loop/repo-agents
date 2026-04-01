## Title: Fix missed scheduling opportunity in LTE PHY simulator

### Summary
The `eNB_scheduler` function in the LTE PHY simulation code was only printing a debug message without performing actual scheduling logic. This caused a bug where UEs with pending data in their buffers were never scheduled downstream, resulting in missed scheduling opportunities and stalled data transmission in simulation scenarios.

The fix adds a call to `get_dci()` within the scheduler function to trigger DCI (Downlink Control Information) generation. This ensures that any UE with pending data gets properly scheduled each subframe, aligning the simulation behavior with expected LTE MAC scheduler functionality.

### Changes
- `openair1/SIMULATION/LTE_PHY/framegen.c`: Added call to `get_dci(Mod_id, frame, subframe)` in `eNB_scheduler()` to generate and allocate DCIs for UEs with buffered data. Added clarifying comment about the scheduling trigger.

### Implementation Details
The `get_dci()` function (defined in the same file) handles the actual DCI creation and resource allocation for both common control channels and UE-specific data transmissions. By invoking it from the scheduler stub, we bridge the gap between the scheduler interface and the DCI generation logic that was previously being bypassed.

### Testing
- Verified that LTE PHY simulation scenarios now properly schedule UEs with pending data
- Confirmed DCI generation occurs each subframe as expected
- Ensured no regression in simulation control flow or memory management