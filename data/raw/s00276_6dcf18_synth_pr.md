## Title: Add range validation for RLC bearer configuration parameters

### Summary
The RLC bearer configuration processing in the NR MAC gNB lacked validation for configuration parameters received from RRC, allowing out-of-spec values to propagate downstream. Specifically, the `process_rlcBearerConfig` function did not validate:
- The count of RLC bearers to add/release against array bounds
- Logical Channel IDs (LCID) against the 3GPP-specified maximum value of 32
- The total number of active logical channels against storage capacity

This missing validation could lead to buffer overflows when processing malformed RRC messages, potentially causing memory corruption or crashes. The fix adds comprehensive range checks for all configuration parameters before they are applied to the scheduler control structure.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/config.c`: Added validation in `process_rlcBearerConfig()` function:
  - Check `rlc_bearer2release_list->list.count` and `rlc_bearer2add_list->list.count` against `MAX_LC_NUM` to prevent buffer overflow
  - Validate each LCID is within [0, 32] range per 3GPP specification
  - Verify `sched_ctrl->dl_lc_num` doesn't exceed array capacity before adding new bearers
  - Added error logging for invalid configurations

### Implementation Details
The validation uses `MAX_LC_ID = 32` (per 3GPP TS 38.331) and `MAX_LC_NUM` derived from the `dl_lc_ids` array size. Invalid configurations are rejected with error logs, preventing out-of-bounds memory access while allowing valid configurations to proceed normally.