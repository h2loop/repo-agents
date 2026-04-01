## Title: Fix type confusion in RB_FOREACH calls in NR RRC CU-UP selection

### Summary
The CU-UP selection functions `select_cuup_slice()` and `select_cuup_round_robin()` in the NR RRC module contain type confusion bugs where they incorrectly apply the address-of operator and cast to `struct rrc_cuup_tree *` when passing the tree parameter to the `RB_FOREACH` macro. The parameter `t` is already a `const struct rrc_cuup_tree *`, so taking its address creates a pointer-to-pointer type that is incompatible with the macro's expectations. The same file correctly uses `RB_FOREACH` without casting in `rrc_gNB_cuup_init()` (line 153). This fix removes the incorrect address-of operations and casts, passing the tree pointer directly.

### Changes
- `openair2/RRC/NR/rrc_gNB_cuup.c`: Removed incorrect `(struct rrc_cuup_tree *)&t` cast from two `RB_FOREACH` macro invocations in `select_cuup_slice()` (line 42) and `select_cuup_round_robin()` (line 67), changing them to simply `t`.

### Testing
- Verified the code compiles without warnings for the `nr-softmodem` target
- Confirmed the fix aligns with the correct usage pattern already present in the same file
- The change is localized to CU-UP candidate iteration during UE association and maintains existing runtime behavior