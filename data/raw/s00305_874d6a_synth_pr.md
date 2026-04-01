## Title: Fix incorrect RACH resource type flag in UL SDU processing

### Summary
The `rx_sdu()` function in the eNB MAC scheduler was incorrectly passing `ra->rach_resource_type > 0` as a flags parameter to RLC data indication calls. This boolean expression was mistakenly added to the function signature where a bitmask flags field is expected. The incorrect flag could cause improper handling of uplink SDUs during random access procedures, potentially leading to protocol errors or dropped messages.

This fix removes the erroneous `ra->rach_resource_type > 0` parameter from two RLC data indication calls, leaving the intended `0` flags value. The RACH resource type is already properly handled elsewhere in the MAC layer and should not be passed as a flag to the RLC layer.

### Changes
- `openair2/LAYER2/MAC/eNB_scheduler_ulsch.c`: 
  - Line 519: Removed `ra->rach_resource_type > 0` from the RLC data indication call for DCCH processing
  - Line 783: Removed `ra->rach_resource_type > 0` from the RLC data indication call for CCCH processing

### Testing
- Verified that the function signatures match the expected parameters for RLC data indication
- Confirmed that RACH resource type handling remains correct in the MAC layer state machine
- Code review confirms the removed parameter was not consumed by the downstream function