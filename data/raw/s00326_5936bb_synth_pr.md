## Title: Add bounds checking for EMM FSM event string lookup

### Summary
The EMM state machine logging contained a potential out-of-bounds array access when converting event primitives to human-readable strings. The code directly used `evt->primitive - _EMMREG_START - 1` as an index into `_emm_fsm_event_str[]` without validating the calculated index bounds. This could result in undefined behavior or crashes if unexpected event values were received from upper layers (RRC) or lower layers (PHY, MAC), especially during cross-layer parameter mismatches or when new events are added but not properly handled in the string mapping array.

The fix introduces explicit bounds checking before array access. When an out-of-range event primitive is detected, the system now logs "UNKNOWN" event instead of attempting to read invalid memory. This defensive programming approach prevents potential crashes and makes the system more robust against unexpected event values propagating from other layers.

### Changes
- `openair3/NAS/UE/EMM/SAP/emm_fsm.c`: Added bounds validation for event string array indexing in `emm_fsm_process()`. The event index is now calculated separately and checked against the array size before calling `emm_fsm_event2str()`. If out of bounds, logs "UNKNOWN" event with the raw primitive value.

### Testing
- Verified compilation with debug flags enabled
- Manually inspected the generated assembly to confirm bounds check is properly optimized
- Validated that normal EMM events (ATTACH_REQUEST, DETACH_REQUEST, etc.) continue to log correctly
- Tested with simulated out-of-range event values to confirm graceful handling of unknown events