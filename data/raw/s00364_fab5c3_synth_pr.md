## Title: Fix incorrect segment buffer cleanup in P7 reassembly queue

### Summary
The P7 reassembly queue cleanup functions incorrectly iterate using a hardcoded maximum of 128 segments when freeing segment buffers. Per the nFAPI specification (derived from 3GPP requirements), `num_segments_expected` is a conditionally mandatory field that indicates the actual number of segments allocated for a message. Using the hardcoded value instead of this field can lead to:
- Accessing uninitialized memory when `num_segments_expected` < 128
- Potential memory corruption or segmentation faults
- Resource leaks if segment buffers beyond `num_segments_expected` were allocated

The fix ensures proper memory management by iterating only over the actual number of segments expected, as specified in the message metadata.

### Changes
- `nfapi/open-nFAPI/vnf/src/vnf_p7.c`: 
  - In `vnf_p7_rx_reassembly_queue_remove_msg()`: Changed loop bound from hardcoded 128 to `iterator->num_segments_expected`
  - In `vnf_p7_rx_reassembly_queue_remove_old_msgs()`: Changed loop bound from hardcoded 128 to `to_delete->num_segments_expected`

### Implementation Details
The `vnf_p7_rx_message_t` structure already contains the `num_segments_expected` field (populated during message allocation). This change aligns the cleanup logic with the actual allocated segment array size, preventing out-of-bounds access and ensuring all allocated segment buffers are properly freed.

### Testing
- Verified correct cleanup behavior for messages with varying segment counts
- Confirmed no regressions in P7 message reassembly functionality
- Memory leak detection shows proper deallocation of all segment buffers