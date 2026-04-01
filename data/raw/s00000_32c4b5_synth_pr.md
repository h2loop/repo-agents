## Title: Fix buffer overflow in LTE turbo decoder causing scheduling constraint violations

### Summary
Fix a buffer overflow in the LTE turbo decoder scalar implementation that was causing resource block allocation violations in downstream scheduling logic. The `phy_threegpplte_turbo_decoder_scalar` function allocated arrays `ext` and `ext2` with size `n` (the coded block size in bits), but the `compute_ext_s` function accesses these arrays beyond their declared bounds during extrinsic information calculation. This memory corruption propagated to scheduling structures, triggering constraint violations.

The fix increases the allocation size for both arrays from `n` to `n+3`, providing sufficient space for the turbo decoder's boundary processing. This accommodates tail bits and algorithmic requirements in the extrinsic computation without changing the core decoder logic. The +3 offset aligns with the 3GPP LTE turbo decoder state machine requirements and ensures memory safety throughout the decoding pipeline.

### Changes
- `openair1/PHY/CODING/3gpplte_turbo_decoder.c`: Increased allocation size of `ext` and `ext2` arrays in `phy_threegpplte_turbo_decoder_scalar()` from `n` to `n+3` to prevent buffer overflow during `compute_ext_s()` execution. This eliminates memory corruption that was affecting downstream scheduling modules.

### Testing
- Verified decoder output remains bit-exact with the previous implementation for all test vectors
- Confirmed scheduling constraint violations no longer occur under heavy load
- Tested with various transport block sizes (40 to 6144 bits) to ensure no regression in decoding performance