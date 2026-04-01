## Title: Fix unreachable code in LDPC encoder due to incorrect conditional include logic

### Summary
The NR LDPC encoder contained unreachable code in the Zc=224 codepath due to incorrect conditional compilation logic. Both `ldpc224_byte.c` (AVX2 implementation) and `ldpc224_byte_128.c` (SSE implementation) were unconditionally included in `ldpc_encode_parity_check.c`, but each file contains preprocessor guards that prevent compilation under opposing build configurations. This resulted in one implementation always being unreachable depending on the `__AVX2__` flag state, potentially causing encoder failures on platforms without AVX2 support.

The root cause was a missing conditional directive around the include statements, which was inconsistent with the pattern used for other LDPC block sizes in the same file. This fix ensures the correct implementation is selected at compile time based on the target architecture.

### Changes
- `openair1/PHY/CODING/nrLDPC_encoder/ldpc_encode_parity_check.c`: Added `#ifdef __AVX2__` conditional compilation around the includes for `ldpc224_byte.c` and `ldpc224_byte_128.c` to ensure only the appropriate implementation is compiled.

### Implementation Details
The fix aligns the Zc=224 codepath with other block sizes (e.g., Zc=256, Zc=192) that already use proper conditional includes. When `__AVX2__` is defined, the AVX2-optimized `ldpc224_byte.c` is included; otherwise, the SSE-compatible `ldpc224_byte_128.c` is used. The SSE version contains an `#ifndef __AVX2__` guard that previously made it unreachable when AVX2 was enabled, and vice versa.