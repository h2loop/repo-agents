## Title: Fix signed/unsigned integer type mismatch in nr_get_ssb_start_symbol

### Summary
The `nr_get_ssb_start_symbol` function in `nr_parms.c` declared the local variable `mu` as a signed `int` when assigning from `fp->numerology_index`. This creates a signed/unsigned integer comparison mismatch since `numerology_index` is defined as an unsigned 8-bit integer type. This mismatch can lead to compiler warnings and potential incorrect branching behavior in downstream logic that compares `mu` against unsigned constants. Changing `mu` to `uint8_t` ensures type consistency and eliminates the comparison mismatch.

### Changes
- `openair1/PHY/INIT/nr_parms.c`: Changed the type of local variable `mu` from `int` to `uint8_t` in the `nr_get_ssb_start_symbol` function to match the type of `fp->numerology_index` and fix signed/unsigned comparison issues.

### Testing
- Verified the change eliminates compiler warnings related to signed/unsigned comparisons in the affected function
- Confirmed no functional changes to the SSB start symbol calculation logic