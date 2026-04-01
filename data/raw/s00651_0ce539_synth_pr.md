## Title: Fix buffer overflow in DFT18432 causing ASN.1 encoding errors

### Summary
The `dft18432` and `idft18432` functions in the PHY tools module contain incorrect output buffer offsets in their butterfly operations, causing buffer overflows that corrupt memory and manifest as ASN.1 encoding errors in downstream protocol processing. The three-output-segment stride pattern was incorrectly specified as (0, 12288, 24576) instead of the proper (0, 6144, 12288) for a 18432-point DFT, resulting in writes beyond the allocated 18432-element buffer. This patch corrects the stride offsets to match the actual DFT structure (3 segments of 6144 elements each), eliminating the memory corruption that was propagating to ASN.1 encoding logic.

### Changes
- `openair1/PHY/TOOLS/oai_dfts.c`: Fixed output buffer offsets in `dft18432` and `idft18432` butterfly operations from `output+12288+i` and `output+24576+i` to `output+6144+i` and `output+12288+i` respectively
- `openair1/PHY/TOOLS/oai_dfts_neon.c`: Applied identical fix to the NEON-optimized variants of both functions

### Implementation Details
The bug affects the `bfly3` and `ibfly3` function calls where the three output pointers reference different segments of the output buffer. The corrected offsets ensure each segment starts at the proper 6144-element boundary, preventing out-of-bounds memory access while maintaining the correct mathematical DFT computation.

### Testing
This fix resolves the ASN.1 encoding errors that were observed downstream of these DFT functions during protocol message generation. The corrected buffer accesses now stay within the allocated memory region while preserving the numerical correctness of the transform.