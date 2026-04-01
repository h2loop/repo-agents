## Title: Fix buffer overrun in textlog command-line argument parsing

### Summary
The textlog utility's argument parser contains a buffer overrun vulnerability when processing multiple `-on`, `-off`, `-ON`, and `-OFF` command-line flags. The code tracks these flags in dynamically allocated arrays (`on_off_name[]` and `on_off_action[]`) sized by the total argument count `n`, but fails to validate that the running index `on_off_n` stays within bounds. When users supply excessive toggle flags, the parser writes beyond allocated memory, corrupting the heap and potentially causing crashes or security issues.

The fix adds explicit bounds checks before each array access. When `on_off_n >= n`, the parser now calls `usage()` to abort with a clear error instead of proceeding with the invalid memory write. This ensures the index never exceeds the allocation size while preserving all existing functionality for valid argument combinations.

### Changes
- `common/utils/T/tracer/textlog.c`: Added bounds validation (`if (on_off_n >= n) usage();`) before accessing `on_off_name[]` and `on_off_action[]` arrays for `-on`, `-off`, `-ON`, and `-OFF` flag processing.

### Testing
- Verified the fix prevents buffer overrun with excessive toggle flags
- Confirmed normal operation with typical flag usage patterns
- Validated that invalid combinations properly trigger the usage() error handler