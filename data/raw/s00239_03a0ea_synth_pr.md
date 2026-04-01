## Title: Fix incorrect timestamp calculation in ethernet IF4p5 interface

### Summary
Fix a critical timestamp calculation bug in the ethernet IF4p5 interface that was causing incorrect transmit power levels downstream. The `trx_eth_read_raw_IF4p5` function was incorrectly assigning `test_header->sub_type` to the timestamp pointer, resulting in invalid timing information being propagated to upper layers. This caused the power control algorithm to make decisions based on corrupted frame/subframe numbers, leading to incorrect power levels.

The fix properly extracts frame and subframe numbers from the `frame_status` field using bit manipulation, then calculates the correct timestamp based on the configured `samples_per_subframe`. This restores proper timing synchronization and corrects downstream power control behavior.

### Changes
- `radio/ETHERNET/eth_raw.c`: Replaced incorrect `*timestamp = test_header->sub_type` assignment with proper timestamp calculation. Extracts frame (bits 6-21) and subframe (bits 22-25) from `frame_status`, then computes timestamp as `(frame * 10 + subframe) * samples_per_subframe`. Uses device configuration when available, with fallback to standard LTE subframe duration (30720 samples) if not configured.

### Implementation Details
The frame and subframe are extracted via bit shifting and masking: `frame = (frame_status >> 6) & 0xffff` and `subframe = (frame_status >> 22) & 0x000f`. The timestamp calculation accounts for 10 subframes per frame. The implementation safely checks for valid `openair0_cfg` before accessing `samples_per_subframe`, preventing null pointer dereference.