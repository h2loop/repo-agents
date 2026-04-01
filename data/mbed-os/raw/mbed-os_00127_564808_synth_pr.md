## Title: Fix out-of-bounds access in MX_WIFI_Socket_ping response handling

### Summary
The `MX_WIFI_Socket_ping` function in the STM WiFi driver contains a potential out-of-bounds write vulnerability. When processing ping responses, the code directly used `rp->num` as the loop bound to copy delay measurements into the caller-provided `response[]` array without validating that `rp->num` does not exceed the fixed-size `MX_WIFI_PING_MAX` limit. This could lead to a buffer overflow if the remote endpoint reports more responses than the array can hold.

The fix introduces a bounds check by limiting the number of copied responses to the minimum of `rp->num` and `MX_WIFI_PING_MAX`, preventing memory corruption while preserving correct behavior for valid inputs.

### Changes
- `connectivity/drivers/wifi/TARGET_STM/COMPONENT_EMW3080B/mx_wifi/mx_wifi.c`: 
  - In `MX_WIFI_Socket_ping`, added `copy_count` variable to clamp the number of responses copied to `response[]` within `MX_WIFI_PING_MAX` bounds.
  - Replaced direct loop bound `rp->num` with `copy_count` to prevent out-of-bounds access.

### Testing
- Verified fix compiles successfully within mbed-os build environment.
- Confirmed that ping responses are correctly truncated when exceeding `MX_WIFI_PING_MAX` entries.
- No functional change for cases where `rp->num <= MX_WIFI_PING_MAX`.