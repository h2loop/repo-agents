## Title: Fix dead code and error handling in VCD tracer gui_thread

### Summary
The `gui_thread` function in the VCD tracer module contains unreachable code that masks error conditions. The function calls `gui_loop()`, which is a main event loop that only returns when a fatal error occurs. The subsequent `return NULL` statement is therefore dead code that is never executed under normal circumstances. More importantly, this silent return masks the fact that an error has occurred, making debugging difficult.

This change replaces the unreachable `return NULL` with `abort()` to properly signal that `gui_loop` should never return. If it does return (indicating an error condition), the process will now abort immediately with a clear failure indication rather than silently continuing with undefined behavior.

### Changes
- `common/utils/T/tracer/vcd.c`: Replaced unreachable `return NULL` statement with `abort()` in `gui_thread()` function to properly handle error conditions when `gui_loop()` returns unexpectedly.

### Implementation Details
The `gui_loop()` function runs the main GUI event loop and is designed to run for the lifetime of the tracer process. It only returns when encountering an unrecoverable error. The original code's `return NULL` created a false impression of normal termination, potentially masking bugs in the error handling path. Using `abort()` ensures that any unexpected return from `gui_loop()` is treated as the fatal error it represents, making failures immediately visible during development and testing.

### Testing
- Verified that normal VCD tracer operation continues unchanged
- Confirmed that the modified code compiles without warnings
- Code review confirms the return path was unreachable in all valid execution flows