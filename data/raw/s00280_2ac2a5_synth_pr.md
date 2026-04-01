## Title: Optimize LDPC encoder by eliminating redundant XOR computations

### Summary
The LDPC BG2 Zc=176 byte encoder function recomputed identical XOR subexpressions multiple times across different rows, causing unnecessary CPU overhead in the critical PHY encoding path. The generated code performed the same XOR operations from scratch for each row instead of reusing intermediate results.

This optimization identifies common XOR subexpressions and precomputes them once per loop iteration. Each unique XOR combination is stored in a temporary `simde__m128i` variable and reused across multiple rows, eliminating redundant calculations while maintaining bit-exact functional equivalence.

### Changes
- `openair1/PHY/CODING/nrLDPC_encoder/ldpc_BG2_Zc176_byte.c`: Added 12 precomputed XOR subexpressions inside the processing loop (e.g., `xor_1_226`, `xor_1572_905`). Updated row calculations to use these cached values, significantly reducing the number of XOR operations executed during LDPC encoding.

### Implementation Details
Precomputed variables are declared after the `c2` pointer assignment within the loop to ensure correct SIMD alignment and offset handling.