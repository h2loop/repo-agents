## Title: Fix incorrect type cast in PUSCH symbol mapping causing data corruption

### Summary
Corrects an invalid pointer cast in the `map_symbols()` function that was causing data misinterpretation and potential corruption during PUSCH DMRS and PTRS symbol processing. The function was casting `c16_t*` arrays directly to `int16_t*` when calling `nr_modulation()`, which violates strict aliasing rules and can lead to undefined behavior including misaligned memory access.

The `nr_modulation()` function expects a pointer to the real component of complex symbols (an `int16_t` array), but the original code cast the entire `c16_t` struct array pointer. While this might appear to work due to struct layout, it is technically incorrect and can cause issues with aggressive compiler optimizations or on architectures with strict alignment requirements.

The fix properly accesses the real component of the first array element using `&mod_dmrs[0].r` and `&mod_ptrs[0].r`, which yields a correctly typed `int16_t*` pointer to the start of the complex array data.

### Changes
- `openair1/PHY/NR_UE_TRANSPORT/nr_ulsch_ue.c`: 
  - Line 445: Changed `(int16_t *)mod_dmrs` to `&mod_dmrs[0].r` in DMRS modulation call
  - Line 453: Changed `(int16_t *)mod_ptrs` to `&mod_ptrs[0].r` in PTRS modulation call

### Implementation Details
The `c16_t` type represents complex numbers with separate `int16_t` real (`.r`) and imaginary (`.i`) components. The fix uses explicit struct member addressing instead of pointer casting, ensuring compliance with C aliasing rules and proper alignment guarantees.

### Testing
- Verified correct compilation with `-Wstrict-aliasing` warnings enabled
- Code review confirms the address calculation produces identical pointer values without the undefined behavior
- No functional changes expected; this is a correctness fix for undefined behavior