## Title: Fix implicit double-to-uint32_t cast in PUCCH group sequence hopping

### Summary
Remove unnecessary `floor()` calls in `nr_group_sequence_hopping()` that caused implicit type casting from double to uint32_t. The function calculates initialization values for PUCCH group hopping using integer division on a uint32_t parameter, but was wrapping the division with `floor()`, which returns a double. Since integer division of unsigned integers already truncates toward zero, the `floor()` calls were redundant and introduced unsafe implicit casts. This change eliminates potential precision loss and clarifies the integer arithmetic semantics without altering the functional behavior.

### Changes
- `openair1/PHY/NR_TRANSPORT/nr_uci_tools_common.c`: 
  - Line 76: `uint32_t c_init = floor(n_id / 30);` → `uint32_t c_init = n_id / 30;`
  - Line 96: `uint32_t c_init = (1 << 5) * floor(n_id / 30) + (n_id % 30);` → `uint32_t c_init = (1 << 5) * (n_id / 30) + (n_id % 30);`

### Implementation Details
Both changes replace `floor(n_id / 30)` with direct integer division `n_id / 30`. The original code relied on implicit conversion of the double result back to uint32_t, which is undefined behavior for large values and inefficient. The fix maintains identical mathematical results while using pure integer arithmetic throughout.

### Testing
- Verified compilation succeeds without warnings for the modified file
- Recommend testing PUCCH transmissions with both `PUCCH_GroupHopping` enabled and disabled to confirm sequence generation produces identical hopping patterns as before
- No performance impact expected; may slightly improve execution speed by avoiding unnecessary floating-point operations in the PUCCH preparation path