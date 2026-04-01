## Title: Fix security header processing order in NAS message handling

### Summary
The NAS message decoder in the NR UE stack processed the security header length before validating the security header type. When the UE received a very short NAS message (e.g., a truncated or malformed PDU from a misbehaving AMF), this ordering allowed a buffer overread: the code would attempt to read past the end of the received buffer to extract the message authentication code and sequence number, even when the security header type indicated the message was plain NAS with no security protection.

This fix reorders the processing logic so that the security header type is validated first. If the header type indicates a plain NAS message, the security fields are skipped entirely. For protected messages, the total message length is now checked against the minimum required size (6 bytes for the security header) before attempting to decode the MAC and sequence number fields. This prevents out-of-bounds reads on truncated or malformed messages.

### Changes
- `openair3/NAS/NR_UE/nr_nas_msg.c`: Reordered security header processing to check `security_header_type` before reading `message_authentication_code` and `sequence_number`. Added minimum length validation for security-protected messages.
- `openair3/NAS/NR_UE/5GS/5GMM/MSG/fgmm_lib.c`: Updated `fgmm_decode_msg()` to propagate the new error code when the buffer is too short for the declared security header type.
- `openair3/NAS/COMMON/NR_NAS_defs.h`: Added `NAS_ERR_BUFFER_TOO_SHORT` error code definition.

### Testing
- Added unit test with a crafted 3-byte NAS PDU containing a security-protected header type; confirmed the decoder returns an error instead of reading out of bounds.
- Ran AddressSanitizer build and confirmed no heap-buffer-overflow reports in the `nr-ue-nas-security` CI test suite.
- Full SA registration and PDU session establishment verified with Open5GS to confirm no regression.
