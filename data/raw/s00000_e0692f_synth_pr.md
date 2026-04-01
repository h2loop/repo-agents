## Title: Fix integer underflow in NB-IoT RSSI request packing

### Summary
The `pack_nb_iot_rssi_request_value` function in the nFAPI NB-IoT implementation lacked bounds checking on the `number_of_ro_dl` field before packing the RO DL array. When this value exceeded the maximum allowed size (`NFAPI_MAX_RO_DL`), it could lead to integer underflow issues and produce unexpectedly large unsigned values downstream, potentially causing buffer overflows or protocol violations.

This patch adds explicit validation to ensure `number_of_ro_dl` does not exceed `NFAPI_MAX_RO_DL` before attempting to pack the RO DL entries. If the value is out of bounds, the function now logs an error and returns failure, preventing the underflow condition and ensuring protocol compliance.

### Changes
- `nfapi/open-nFAPI/nfapi/src/nfapi_p4.c`: Added bounds check for `number_of_ro_dl` field and wrapped RO DL packing loop in conditional validation with error logging.

### Implementation Details
The fix introduces a conditional check around the RO DL packing loop. When `number_of_ro_dl` exceeds `NFAPI_MAX_RO_DL`, the function logs an error message via `NFAPI_TRACE` and returns 0 to indicate packing failure. This prevents the loop from executing with an invalid count and maintains the integrity of the packed message buffer.