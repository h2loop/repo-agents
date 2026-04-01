## Title: Fix stack buffer overflow in SSB bitmap parsing

### Summary
The `get_ssb_bitmap()` function in the NR MAC gNB radio configuration module contains a stack buffer overflow when processing the long SSB bitmap format (case 3). The code unconditionally iterates over 8 bytes of the `longBitmap.buf` array without validating the actual buffer size, causing out-of-bounds reads when the buffer contains fewer than 8 bytes. This can lead to memory corruption, undefined behavior, or crashes when processing malformed SIB messages.

This fix adds proper bounds checking by using the buffer's actual size (`longBitmap.size`) and limiting the loop to process at most 8 bytes. This prevents out-of-bounds access while preserving correct bitmap construction for valid configurations.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/nr_radio_config.c`: In the `get_ssb_bitmap()` function's case 3 handler, replaced the hardcoded 8-iteration loop with a bounds-checked version. Added `loop_count` variable set to `min(longBitmap.size, 8)` to ensure we never read beyond the allocated buffer. The loop now iterates only over valid buffer indices while still constructing the full 64-bit SSB bitmap from up to 8 bytes.

### Implementation Details
The fix introduces a local `loop_count` variable that safely determines the iteration limit based on the actual buffer size from the ASN.1 BIT_STRING structure. This defensive approach ensures robustness against malformed input while maintaining full compatibility with valid SIB configurations. The change is minimal and focused, affecting only the vulnerable code path.

### Testing
- Verified that valid SIB messages with proper 8-byte long bitmaps continue to work correctly
- Prevents crashes when processing truncated SIB messages with fewer than 8 bytes in the long bitmap
- No performance impact expected as the change only adds a simple min() comparison