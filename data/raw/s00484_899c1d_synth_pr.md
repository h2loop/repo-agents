## Title: Fix RLC UM entity creation to return NULL on allocation failure

### Summary
The `new_rlc_entity_um()` function in the RLC v2 layer currently calls `exit(1)` when memory allocation fails, which terminates the entire OAI process. This prevents upper layers from implementing graceful degradation or recovery strategies for out-of-memory conditions.

This patch modifies the error handling to return NULL instead, allowing callers to check the return value and handle allocation failures appropriately. The change maintains the existing error logging while following standard C library conventions for memory allocation functions.

### Changes
- `openair2/LAYER2/rlc_v2/rlc_entity.c`: In `new_rlc_entity_um()`, replaced `exit(1)` with `return NULL` on calloc failure (line 108)

### Implementation Details
The function already had a NULL check after the `calloc()` call. The fix simply changes the error handling path from process termination to returning NULL. Callers of `new_rlc_entity_um()` should be updated to check for NULL return values, though this is standard practice for entity creation functions in the codebase.

### Testing
- Code compiles without warnings
- Error logging path verified to remain functional
- Enables proper error propagation for out-of-memory scenarios