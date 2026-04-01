## Title: Fix stale QoS flow mappings in DRB generation

### Summary
The `generateDRB()` function in the gNB RRC radio bearers module fails to clear the `mappedQoS_FlowsToAdd` array before populating it with QoS flow identifiers. This can cause stale mappings from previous PDU session configurations to persist, violating 3GPP TS 38.331 procedures for QoS flow to DRB mapping. The fix zero-initializes the array before adding current QoS flows, ensuring clean state for each DRB establishment.

### Changes
- `openair2/RRC/NR/rrc_gNB_radio_bearers.c`: Added `memset()` to clear `mappedQoS_FlowsToAdd` array prior to populating it with current QoS flow IDs in `generateDRB()`.

### Implementation Details
The fix inserts a `memset()` call to zero out the `mappedQoS_FlowsToAdd` array before the loop that populates it with QFI values from `pduSession->param.qos[]`. This prevents any residual data from previous DRB configurations from being inadvertently included in new signaling messages.

### Testing
- Ensures compliance with 3GPP message flow procedures for QoS flow mapping updates
- Prevents incorrect QoS flow to DRB associations during PDU session modification procedures