## Title: Fix buffer overflow in DLSCH UE selection functions

### Summary
The DLSCH UE selection functions `set_dl_ue_select_msg2` and `set_dl_ue_select_msg4` in the eNB MAC scheduler lack bounds checking when populating the UE selection list. When more than 20 UEs are scheduled for downlink transmission within a single scheduling interval, the code writes beyond the fixed-size array `dlsch_ue_select[CC_id].list[20]`, causing memory corruption and potential segmentation faults.

The root cause is the absence of validation for the `ue_num` counter against the maximum list size (20) before accessing the array. This fix adds proper bounds checking to both functions and logs an error when the list capacity is exceeded, preventing out-of-bounds writes while maintaining system stability under high load conditions.

### Changes
- `openair2/LAYER2/MAC/eNB_scheduler_fairRR.c`: Added bounds checking (`ue_num < 20`) in `set_dl_ue_select_msg2` and `set_dl_ue_select_msg4` before accessing the UE selection list. Added error logging when the list is full.

### Testing
- Verified the fix prevents array overflow when scheduling more than 20 UEs
- Confirmed normal operation continues when UE count is within limits
- Ran MAC scheduler unit tests to ensure no regressions