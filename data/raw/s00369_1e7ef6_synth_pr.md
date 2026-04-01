## Title: Fix vendor extension TLV buffer pointer advancement causing CRC errors

### Summary
The TLV list unpacking functions fail to advance the read buffer pointer after successfully processing vendor extension TLVs. When `unpack_p7_vendor_extension_tlv` returns success (>0), the generic unpacking logic leaves `ppReadPackedMsg` pointing at the start of the vendor extension value, causing subsequent TLV parsing to read from incorrect offsets. This misalignment triggers CRC validation failures or parse errors for the remainder of messages containing vendor extensions.

This patch ensures the buffer pointer is advanced past the TLV value (including padding for NR variants) after successful vendor extension handling, aligning the stream position for continued parsing.

### Changes
- `nfapi/open-nFAPI/common/src/nfapi.c`: Added pointer advancement logic in four TLV unpacking functions:
  - `unpack_tlv_list`: Advance by `generic_tl.length` on successful vendor extension
  - `unpack_nr_tlv_list`: Advance by `generic_tl.length + get_tlv_padding(generic_tl.length)` on successful vendor extension  
  - `unpack_p7_tlv_list`: Advance by `generic_tl.length` on successful vendor extension
  - `unpack_nr_p7_tlv_list`: Advance by `generic_tl.length + get_tlv_padding(generic_tl.length)` on successful vendor extension

### Implementation Details
The fix adds `else` clauses that trigger when vendor extension unpacking succeeds (return value > 0). For NR variants, the existing `get_tlv_padding()` helper ensures proper 4-byte alignment per the nFAPI specification. The error path (return value == 0) remains unchanged, preserving early exit behavior.

### Testing
- Verified messages with vendor extension TLVs parse correctly without CRC errors
- Confirmed subsequent TLVs are parsed from correct offsets
- Tested both LTE and NR TLV unpacking paths with vendor extensions present