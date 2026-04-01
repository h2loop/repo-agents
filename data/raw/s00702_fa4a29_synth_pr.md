## Title: Add range validation for PRNG seed parameter in Tausworthe generator

### Summary
The `set_taus_seed()` function initializes the Tausworthe random number generator using a user-provided seed value. The function accepts an `unsigned int` parameter but casts it to `(long int)` when calling `srand48_r()`. On 32-bit and LP64 systems, `long int` has a maximum value of 2^31-1 (2147483647), while `unsigned int` can range up to 2^32-1 (4294967295). When seed values exceed the `long int` range, the cast produces negative values, causing undefined behavior in the PRNG initialization and potentially leading to non-deterministic simulation results.

This fix adds explicit range validation to ensure the seed value always fits within the valid `long int` range before casting. If the seed exceeds 2147483647, it is reduced using modulo 2147483648 to bring it into the valid range while preserving the randomness properties of the original seed.

### Changes
- `openair1/SIMULATION/TOOLS/taus.c`: Added range validation in `set_taus_seed()` that checks if `seed_init > 2147483647U`. For out-of-range seeds, applies modulo operation `seed_init % 2147483648U` to ensure deterministic behavior within the valid range for `srand48_r()`.

### Implementation Details
- Uses explicit unsigned integer constants (`2147483647U`, `2147483648U`) to avoid signed/unsigned comparison warnings and make the range boundary clear
- The modulo operation preserves entropy by mapping large seeds into the valid range rather than clamping to the maximum value
- Maintains full backward compatibility for all seed values already within the valid range
- No performance impact as the check is a single integer comparison on a rarely-called initialization path

### Testing
- Verified syntax correctness through compilation checks
- Ensures all seed values passed to `srand48_r()` are non-negative and within the expected range, eliminating undefined behavior for out-of-spec configuration parameters