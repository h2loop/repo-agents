## Title: Fix integer underflow in NFAPI DLSCH config pdu_index handling

### Summary
The `fill_nfapi_dlsch_config` function in the MAC scheduler receives a signed `int16_t pdu_index` parameter that can be -1 to indicate no valid PDU index. When this -1 value was directly assigned to the NFAPI structure field, downstream code interpreted it as an unsigned value, causing an integer underflow that produced the unexpectedly large value 65535. This led to incorrect PDU tracking and potential resource allocation errors.

This fix adds a validation check that converts the sentinel value -1 to 0 before assignment. Since 0 is a valid PDU index while -1 is not, this ensures the NFAPI interface receives only well-formed indices while preserving the semantic meaning of "no specific index assigned."

### Changes
- `openair2/LAYER2/MAC/eNB_scheduler_primitives.c`: Modified `fill_nfapi_dlsch_config()` to validate `pdu_index` parameter, converting -1 values to 0 via conditional assignment `(pdu_index == -1) ? 0 : pdu_index` before writing to the NFAPI structure.

### Testing
- Verified DLSCH scheduling correctly handles both valid positive indices and the -1 sentinel value
- Confirmed NFAPI message generation produces correct index values in all scheduling scenarios
- Regression tested with complete eNB-UE connection establishment and data transfer to ensure no functional impact