## Title: Fix buffer overflow in CLI argument tokenization

### Summary
The CLI command parser in `token_argument()` was susceptible to a buffer overflow when processing overly long command strings. The function tokenizes input arguments into a fixed-size array (`optv`) without checking array bounds, allowing writes beyond the allocated memory when more than 20 tokens are present.

This fix adds a bounds check to the tokenization loop, ensuring we stop parsing once the maximum number of tokens (19) is reached. This prevents memory corruption and potential crashes when users input malformed or excessively long CLI commands.

### Changes
- `openair2/UTIL/CLI/cli_cmd.c`: Added bounds check `tokc < 19` in `token_argument()` to prevent writing beyond the `optv` array limits during argument tokenization.

### Implementation Details
The `optv` array is defined with a fixed size that accommodates up to 20 elements (indices 0-19). The original loop condition only checked for NULL tokens, allowing `tokc` to increment indefinitely. The fix adds `tokc < 19` to the while condition, ensuring we never attempt to write to `optv[20]` or beyond.

### Testing
- Verified the fix prevents out-of-bounds writes with artificially long command strings
- Confirmed normal CLI operations continue to function correctly
- Static analysis confirms no buffer overflow vulnerabilities remain in this code path