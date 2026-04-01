## Title: Replace magic number bitmask with symbolic constant in EPS Mobile Identity parsing

### Summary
The EPS Mobile Identity decoding and encoding functions used the hard-coded bitmask `0x7` to extract the 3-bit identity type field from NAS message buffers. This magic number appeared in five locations across the codebase without documentation, making the code's intent unclear and maintenance error-prone. The value `0x7` corresponds to the lower three bits of the first octet that encode whether the identity represents GUTI, IMSI, IMEI, or other types.

This change introduces the symbolic constant `EPS_MOBILE_IDENTITY_TYPE_MASK` to explicitly document the purpose of this bitmask, improving code readability and preventing potential inconsistencies if the mask value needs to change in the future.

### Changes
- **openair3/NAS/COMMON/IES/EpsMobileIdentity.h**: Added `#define EPS_MOBILE_IDENTITY_TYPE_MASK 0x7` to provide a named constant for the identity type bitmask
- **openair3/NAS/COMMON/IES/EpsMobileIdentity.c**: Replaced five instances of `& 0x7` with `& EPS_MOBILE_IDENTITY_TYPE_MASK` in:
  - `decode_eps_mobile_identity()` (line 54)
  - `decode_guti_eps_mobile_identity()` (line 194)
  - `decode_imsi_eps_mobile_identity()` (line 222)
  - `decode_imei_eps_mobile_identity()` (line 268)
  - `encode_guti_eps_mobile_identity()` (line 305)

### Implementation Details
The `typeofidentity` field is defined as a 3-bit bitfield (`uint8_t typeofidentity:3`) in the EPS Mobile Identity structures. The mask `0x7` (binary `0b111`) safely extracts these bits during both decode (parsing incoming NAS messages) and encode (building outgoing messages) operations. No functional behavior is changed; this is purely a code clarity improvement.

### Testing
- Verified successful compilation of the modified NAS COMMON subsystem
- Confirmed no functional changes; protocol behavior remains identical
- This refactoring improves maintainability without impacting runtime performance or compatibility