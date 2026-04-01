## Title: Fix buffer overflow vulnerability in IMEISV mobile identity encoder

### Summary
The `encode_imeisv_mobile_identity` function in the NAS mobile identity encoder was writing up to 9 bytes to the target buffer without verifying available space, creating a buffer overflow vulnerability. When encoding IMEISV mobile identities, the function would unconditionally write digit fields and parity bits directly to the buffer pointer, potentially corrupting adjacent memory if the caller provided an undersized buffer. This could lead to crashes, undefined behavior, or security vulnerabilities.

This patch adds proper bounds checking by:
1. Adding a `len` parameter to the function signature to receive the available buffer size
2. Inserting a `CHECK_PDU_POINTER_AND_LENGTH_ENCODER` validation that ensures at least 9 bytes are available before any write operations
3. Updating the call site in `encode_mobile_identity` to pass the remaining buffer length

The 9-byte requirement matches the IMEISV encoding format specified in 3GPP TS 24.008, which includes the identity type octet plus 8 bytes for the 16-digit IMEISV value with parity bits.

### Changes
- `openair3/NAS/COMMON/IES/MobileIdentity.c`: 
  - Updated `encode_imeisv_mobile_identity()` signature to include `uint32_t len` parameter
  - Added buffer length validation macro `CHECK_PDU_POINTER_AND_LENGTH_ENCODER(buffer, 9, len)` at function entry
  - Modified call site in `encode_mobile_identity()` to pass `len - encoded` as the available length

### Implementation Details
The fix follows the established pattern used throughout the NAS encoder functions, leveraging the existing `CHECK_PDU_POINTER_AND_LENGTH_ENCODER` macro that validates pointer non-nullness and sufficient remaining length before proceeding with encoding operations. The IMEISV format requires exactly 9 bytes: 1 byte for type/parity and 8 bytes encoding 16 BCD digits.