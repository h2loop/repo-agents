## Title: Replace magic number with NFAPI_NO_TLV constant in nFAPI P7 codec

### Summary
The `unpack_nr_dl_node_sync` function passes a literal `0` as the TLV count parameter to `unpack_nr_p7_tlv_list`, representing that no Type-Length-Value elements should be processed for the NR DL Node Sync message. This magic number lacks semantic meaning and reduces code maintainability.

This patch introduces the `NFAPI_NO_TLV` symbolic constant to explicitly document the intent of zero TLV processing. The constant is defined in the public nFAPI header to enable reuse across other codec functions with similar requirements.

### Changes
- `nfapi/open-nFAPI/common/public_inc/nfapi.h`: Added `#define NFAPI_NO_TLV 0` with comment indicating it represents no TLVs to process
- `nfapi/open-nFAPI/nfapi/src/nfapi_p7.c`: Replaced magic number `0` with `NFAPI_NO_TLV` constant in the `unpack_nr_dl_node_sync` function call to `unpack_nr_p7_tlv_list`

### Implementation Details
The constant maintains binary compatibility by preserving the value `0` while improving code clarity. Placing it in the public header allows consistent usage throughout the nFAPI codec implementation for any future functions that need to explicitly specify zero TLVs.