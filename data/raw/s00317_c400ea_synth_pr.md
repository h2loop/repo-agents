## Title: Add mandatory IEs to M2AP MBMS SESSION START messages

### Summary
The M2AP MBMS SESSION START RESPONSE message was missing mandatory information elements (IEs) as defined in the M2AP protocol specification. The response message structure contained only a placeholder dummy field and did not include the required MCE MBMS M2AP ID and ENB MBMS M2AP ID identifiers. This caused protocol compliance issues when communicating with MCE (Multi-cell/Multicast Coordination Entity) entities, as the response could not be properly correlated with the original request.

This fix adds the mandatory IEs to both the request and response message structures and ensures the response handler properly propagates these identifiers from the incoming request to the outgoing response.

### Changes
- `openair2/COMMON/m2ap_messages_types.h`: Replaced placeholder dummy fields in `m2ap_session_start_req_t` and `m2ap_session_start_resp_t` with mandatory IE fields `mce_mbms_m2ap_id` and `enb_mbms_m2ap_id`
- `openair2/RRC/LTE/rrc_eNB_M2AP.c`: Updated `rrc_eNB_process_M2AP_MBMS_SESSION_START_REQ()` to populate the mandatory IEs in the response message by copying them from the incoming request

### Implementation Details
The response handler now extracts the MCE MBMS M2AP ID and ENB MBMS M2AP ID from the session start request and sets these values in the response message before sending it to the M2AP task. This ensures proper protocol compliance and message correlation.

### Testing
This change fixes a protocol compliance issue. Testing should verify that MBMS session establishment completes successfully with MCE entities that enforce mandatory IE validation.