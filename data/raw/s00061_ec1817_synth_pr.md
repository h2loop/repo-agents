## Title: Fix heap buffer overflow in nFAPI HARQ indication packing

### Summary
Fix a heap buffer overflow vulnerability in the nFAPI P7 interface when packing HARQ indication messages. The `pack_harq_indication_body_value()` function was incorrectly using `push16()` to write the instance length field, which increments the buffer pointer and causes writes beyond the allocated memory region. This could lead to memory corruption, process crashes, or security exploits when processing HARQ feedback from the PHY layer.

The root cause was that `instance_length_p` points to a position earlier in the buffer where the length field needs to be backfilled after the actual data is written. Using `push16()` here advances the pointer erroneously, corrupting subsequent memory. The fix writes the 16-bit length value directly to the saved position without pointer increment, adds proper bounds checking, and handles both big-endian and little-endian byte ordering correctly.

### Changes
- `nfapi/open-nFAPI/nfapi/src/nfapi_p7.c`: Modified `pack_harq_indication_body_value()` to safely write the instance length field by directly accessing the pre-saved pointer location `instance_length_p` with explicit byte-order handling and buffer space validation, replacing the unsafe `push16()` call.

### Implementation Details
The fix checks buffer capacity before writing, then manually encodes the 16-bit length value using conditional compilation for endianness (`FAPI_BYTE_ORDERING_BIG_ENDIAN`). If insufficient space remains, it logs an error and returns failure instead of corrupting memory.

### Testing
- Verified correct HARQ indication message packing with valgrind to confirm no buffer overruns
- Tested with both normal and maximum-sized HARQ indication payloads
- Confirmed proper byte order encoding on little-endian and big-endian target architectures
- Validated that HARQ feedback processing completes without crashes under load