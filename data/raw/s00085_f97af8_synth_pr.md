## Title: Fix buffer overrun in SRS indication FDD Rel8 unpacking

### Summary
The `unpack_srs_indication_fdd_rel8_value` function in the nFAPI parser reads a `number_of_resource_blocks` value from incoming messages and uses it to unpack SNR values into a fixed-size array without bounds validation. This allows malformed messages to trigger a buffer overrun when `number_of_resource_blocks` exceeds `NFAPI_NUM_RB_MAX`, potentially corrupting memory and causing undefined behavior.

This fix adds explicit validation of the `number_of_resource_blocks` field against the maximum allowed value before reading the SNR array. If the value exceeds the limit, the function logs an error and returns failure, preventing the out-of-bounds write.

### Changes
- `nfapi/open-nFAPI/nfapi/src/nfapi_p7.c`: Added bounds check for `number_of_resource_blocks` in `unpack_srs_indication_fdd_rel8_value()`. Restructured the unpacking logic to validate the field before calling `pullarray8()`, and added error logging for invalid values.

### Implementation Details
The fix splits the original single-return-statement logic into multiple steps:
1. First unpack the header fields including `number_of_resource_blocks`
2. Validate that `number_of_resource_blocks <= NFAPI_NUM_RB_MAX`
3. Only then proceed to unpack the SNR array into the fixed-size buffer

This ensures the `pullarray8()` call cannot write beyond the allocated `snr[NFAPI_NUM_RB_MAX]` array bounds, eliminating the vulnerability.