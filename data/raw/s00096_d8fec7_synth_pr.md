## Title: Fix UL failure timer duration to comply with 3GPP specifications

### Summary
The uplink failure timer (`ul_failure_timer`) in the LTE RRC module was incorrectly configured to 20 seconds (20000 subframes), violating 3GPP timing requirements for UE context release after radio link failure. According to 3GPP TS 36.331 and related specifications, the network should detect uplink failure and initiate UE context release much more quickly. This change reduces the timer duration to 1 second (1000 subframes) to ensure compliance with standard timing requirements.

The timer is implemented as a subframe counter where each increment represents 1ms. The excessive 20-second timeout caused delayed detection of uplink failures, leading to resource exhaustion in scenarios with frequent connection drops.

### Changes
- `openair2/RRC/LTE/rrc_eNB.c`: Updated `ul_failure_timer` threshold from `20000` to `1000` in 5 locations:
  - Line 837: Timer check in `rrc_eNB_free_UE()`
  - Line 1434: Timer initialization in RRC connection reestablishment failure path
  - Line 5854: Timer initialization during CCCH processing
  - Line 7239: Timer check in `rrc_subframe_process()` with updated comment
  - Line 7367: Additional timer check in the same function

### Testing
- Verified timer expiration occurs after 1 second of simulated uplink failure
- Confirmed UE context release messages are sent correctly with cause "radio connection with UE lost"
- Validated no regression in RRC connection establishment/reestablishment procedures
- Ran `lte-softmodem` with 4 UEs to ensure proper cleanup of failed connections within expected timeframe