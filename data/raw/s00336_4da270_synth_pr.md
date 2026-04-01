## Title: Fix missing return statement in narrowband_to_first_rb

### Summary
Fix a missing return statement in the `narrowband_to_first_rb` function that could lead to undefined behavior when encountering an invalid downlink bandwidth configuration. The function's `default` case contained an `AssertFatal` call followed by a `break` statement, but no explicit return value on that code path. While `AssertFatal` terminates execution in debug builds, release builds could continue past the `break` and reach the function's closing brace without returning a value, violating the function's non-void contract.

This change adds an explicit `return -1;` after the assertion to ensure all code paths return a value, clearly signaling an invalid bandwidth configuration to the caller and preventing potential undefined behavior.

### Changes
- `openair2/LAYER2/MAC/eNB_scheduler_primitives.c`: Added `return -1;` in the `default` case of the `narrowband_to_first_rb` function's switch statement.

### Implementation Details
The added return value of `-1` serves as an error indicator for invalid `dl_Bandwidth` values that fall outside the expected range (0, 1, 3, 5). This defensive programming practice ensures the function has well-defined behavior on all code paths while maintaining the existing assertion for debugging purposes.