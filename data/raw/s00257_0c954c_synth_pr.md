## Title: Fix null pointer dereference in F1AP UE context modification request cleanup

### Summary
The `free_ue_context_mod_req()` function in the F1AP library dereferences the `req` parameter without first validating it is non-NULL. This can cause segmentation faults when cleanup code attempts to free an already-freed or uninitialized request structure. The issue follows a common pattern where defensive NULL checks are missing from resource cleanup functions.

This fix adds an early return guard clause to handle NULL `req` pointers gracefully, preventing crashes during error handling paths or shutdown sequences where the request structure may have been partially freed or never allocated.

### Changes
- `openair2/F1AP/lib/f1ap_ue_context.c`: Added NULL pointer check at the start of `free_ue_context_mod_req()` that returns immediately if `req` is NULL, preventing dereference of invalid memory.

### Implementation Details
The guard clause `if (!req) return;` is placed at the function entry point before any field dereferences occur. This pattern is consistent with other defensive cleanup functions in the OAI codebase and has negligible performance impact. The change is minimal and maintains the existing function signature and behavior for all valid (non-NULL) inputs.

### Testing
- Verified the fix by inspecting call sites to confirm NULL pointer scenarios can legitimately occur during error handling
- Confirmed the change compiles without warnings
- The fix follows established patterns used in other `free_*` functions within the F1AP module