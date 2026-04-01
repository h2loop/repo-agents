## Title: Fix missing PCO handling in PDN disconnect request simulator

### Summary
The NAS test simulator's `_pdn_disconnect_request` function was not processing Protocol Configuration Options (PCO) from PDN disconnect request messages, causing inconsistent behavior downstream. While the message structure (`pdn_disconnect_request_msg`) properly defines PCO fields and presence masks, the simulator's logging function silently ignored this information, leading to incomplete message parsing and debugging output. This patch adds proper PCO handling to ensure all protocol layer information is consistently processed.

### Changes
- `openair3/NAS/TEST/AS_SIMULATOR/nas_process.c`: Added PCO field processing in `_pdn_disconnect_request()` function. The change checks for `PDN_DISCONNECT_REQUEST_PROTOCOL_CONFIGURATION_OPTIONS_PRESENT` in the message presence mask and appends the PCO value to the output buffer when present.

### Implementation Details
The fix adds a conditional block that validates the PCO presence flag before accessing the `protocolconfigurationoptions` field from the message structure. The PCO value is formatted as a string and appended to the function's output buffer following the same pattern used by other optional fields in the message. This maintains backward compatibility by only processing PCO when explicitly present in the message.

### Testing
- Verified PCO parsing with test PDN disconnect requests containing protocol configuration options
- Confirmed no regression in handling messages without PCO present
- Validated output format consistency with other NAS message processing functions in the simulator