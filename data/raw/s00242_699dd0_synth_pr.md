## Title: Fix HARQ process error due to stale per-slot data persistence

### Summary
The HARQ process in the NR UE PHY interface was using stale redundancy versions and transmission parameters from previous slots, causing incorrect retransmission behavior and BLER table lookups. The `read_channel_param()` function only reset the `latest` flag across all slots but failed to clear per-slot arrays (`rvIndex`, `drop_flag`, `rnti`, `mcs`) when processing a new downlink assignment. This resulted in leftover HARQ state from prior transmissions being incorrectly applied to new transport blocks, leading to wrong redundancy version selection and erroneous packet drop decisions.

This fix ensures clean HARQ state initialization by clearing all per-slot data when the first PDU for a given slot is received (`index == 0`). The arrays are zeroed using `memset()`, preventing any stale values from persisting across slot processing cycles.

### Changes
- `openair2/NR_UE_PHY_INTERFACE/NR_Packet_Drop.c`: Added slot data clearing logic in `read_channel_param()` when `index == 0`. This resets `num_pdus`, `sinr`, `area_code`, and clears `rvIndex`, `rnti`, `mcs`, and `drop_flag` arrays for the target slot. Enhanced debug logging to include redundancy version information.

### Implementation Details
The fix leverages the `index` parameter (which counts PDUs within a dl_tti_request) to detect the first PDU for a slot. When `index == 0`, all slot-specific HARQ state is explicitly cleared before populating new values. This ensures deterministic behavior for each slot's transmission parameters without affecting the performance of subsequent PDUs in the same TTI.

### Testing
- Verified HARQ retransmissions now use correct redundancy versions across multiple slot cycles
- Confirmed no regression in BLER-SINR table lookups for transport block drop decisions
- Ran basic NR UE PHY interface tests to ensure proper initialization and no memory corruption