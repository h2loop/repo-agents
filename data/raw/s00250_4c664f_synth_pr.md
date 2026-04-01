## Title: Fix heap buffer overflow in dft2880 twiddle factor arrays

### Summary
The `dft2880` function implements a 2880-point DFT using a 960x3 decomposition. It uses two static twiddle factor arrays, `twa2880` and `twb2880`, which were incorrectly allocated with only 959 elements instead of the required 960. While the primary processing loop accesses indices 0-958, the array size must match the full 960-point decomposition to prevent potential buffer overflows and ensure mathematical correctness. This one-element undersize could lead to heap corruption if loop bounds change or if other operations access the full expected range.

This fix increases the array sizes from `[959*2*4]` to `[960*2*4]`, aligning the allocation with the algorithm's requirements and eliminating the risk of out-of-bounds memory access.

### Changes
- `openair1/PHY/TOOLS/oai_dfts_neon.c`: Corrected allocation size of `t