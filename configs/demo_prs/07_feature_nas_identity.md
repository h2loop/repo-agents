## Title: Add NAS Identity Request message handler and codec library

### Summary
The NR UE NAS stack was missing a handler for the 5GMM Identity Request message (message type 0x5b) defined in 3GPP TS 24.501 Section 8.2.21. When the AMF sent an Identity Request (e.g., requesting SUCI or 5G-GUTI during registration), the UE logged an "unknown NAS message type" warning and dropped the message, causing the registration procedure to stall and eventually time out.

This patch implements the full Identity Request decode and Identity Response encode path. The decoder extracts the mandatory Identity Type IE and the UE constructs an Identity Response containing the requested mobile identity (SUCI, 5G-GUTI, or IMEI) based on the identity type value. The implementation follows the message structure and IE definitions in TS 24.501 Tables 8.2.21.1 and 8.2.22.1.

### Changes
- `openair3/NAS/NR_UE/5GS/5GMM/MSG/fgmm_identity_request.c`: New file. Implements `fgmm_decode_identity_request()` to parse the Identity Type mandatory IE from the request PDU.
- `openair3/NAS/NR_UE/5GS/5GMM/MSG/fgmm_identity_request.h`: New file. Defines the `fgmm_identity_request_msg_t` structure and decode function prototype.
- `openair3/NAS/NR_UE/5GS/5GMM/MSG/fgmm_lib.c`: Added case for message type `FGS_IDENTITY_REQUEST` in `fgmm_decode_msg()` dispatch. Added `fgmm_encode_identity_response()` to `fgmm_encode_msg()` dispatch.
- `openair3/NAS/NR_UE/5GS/5GMM/MSG/fgmm_lib.h`: Added `FGS_IDENTITY_REQUEST` and `FGS_IDENTITY_RESPONSE` message type constants. Added `fgmm_identity_response_msg_t` to the `fgmm_msg_t` union.
- `openair3/NAS/NR_UE/nr_nas_msg.c`: Added `nr_nas_handle_identity_request()` to process the decoded Identity Request and build the Identity Response using the UE's stored mobile identity.
- `openair3/NAS/NR_UE/5GS/5GMM/MSG/CMakeLists.txt`: Added `fgmm_identity_request.c` to the source list.

### Testing
- Tested Identity Request/Response exchange against Open5GS AMF requesting SUCI, 5G-GUTI, and IMEI identity types; all three complete successfully.
- Ran the `nr-sa-registration` CI pipeline; UE registration now succeeds on AMF configurations that issue an Identity Request before Authentication.
- Added unit test in `openair3/NAS/NR_UE/5GS/5GMM/MSG/tests/` validating encode/decode round-trip for all supported identity types.
