## Title: Fix off-by-one error in `data_cb` string handling

### Summary
This PR fixes an off-by-one error in the `data_cb` function within the Bluetooth advertising test code. The issue occurred when copying advertisement data into the `name` buffer—while the code correctly limited the copy length to `NAME_LEN - 1`, it failed to explicitly null-terminate the string. This could lead to undefined behavior when `strlen(name)` was later called in `scan_recv`.

The fix ensures proper null-termination by calculating the copy length, copying the data, and then setting `name[len] = '\0'`.

### Changes
- **tests/bsim/bluetooth/ll/advx/src/main.c**: 
  - Modified `data_cb` to correctly null-terminate the `name` string after copying data.
  - Added `uint8_t len` to calculate and store the copy length.
  - Replaced direct `memcpy` with a length-limited copy followed by explicit null termination.

### Impact
Resolves potential string handling issues in Bluetooth advertisement parsing, ensuring robust operation of the advertising test suite. No functional changes to API or configuration; purely a safety and correctness improvement.