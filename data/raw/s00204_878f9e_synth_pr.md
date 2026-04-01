## Title: Fix ENCODE_U24 macro buffer overflow and size miscalculation

### Summary
The `ENCODE_U24` macro in the NAS TLV encoder was writing 4 bytes to the buffer while only incrementing the size counter by 3 bytes. This mismatch caused buffer overflows and type confusion when encoding 24-bit fields in NAS messages, particularly affecting mobile identity encoding paths like `encode_tmgi_mobile_identity()`. The macro cast the buffer to `uint32_t*` and used `htonl()`, which writes a full 32-bit word, corrupting adjacent memory and leading to undefined behavior when subsequent fields were parsed.

The fix ensures only 3 bytes are written using `memcpy` from the lower bytes of a temporary 32-bit value, and correctly increments the size by exactly 3 bytes. This prevents memory corruption and aligns the encoded payload length with the actual buffer consumption.

### Changes
- `openair3/NAS/COMMON/UTIL/TLVEncoder.h`: Rewrote `ENCODE_U24` macro to safely encode 24-bit values using `memcpy` instead of pointer casting, and corrected size increment from `sizeof(uint8_t) + sizeof(uint16_t)` to literal `3`.

### Implementation Details
The new implementation:
1. Converts the value to network byte order in a temporary `uint32_t`
2. Copies only the lower 3 bytes (skipping the MSB) to the target buffer
3. Explicitly increments size by 3 to match actual bytes written

This approach avoids unaligned memory access issues and ensures the macro behaves correctly regardless of buffer alignment or architecture.

### Testing
- Verified correct encoding of 24-bit fields in mobile identity IEs
- Confirmed no buffer overruns in NAS message construction paths
- Validated size tracking consistency across multiple NAS message types