## Title: Fix missing return statements in gNB initialization functions

### Summary
The `get_options()` function in the gNB softmodem was declared with a non-void return type but lacked return statements, causing undefined behavior and preventing proper error propagation from command-line parsing. Additionally, `create_gNB_tasks()` had a missing return statement on an error path when X2AP task creation fails in NSA mode. These issues could lead to silent failures during gNB initialization and incorrect execution flow when configuration parsing encounters errors.

### Changes
- `executables/nr-softmodem.c`:
  - Changed `get_options()` signature from `static void` to `static int` to properly return the status of `config_process_cmdline()`
  - Added return statement to propagate command-line parsing errors upstream
  - Added missing `return -1` in `create_gNB_tasks()` when `itti_create_task(TASK_X2AP)` fails in NSA mode, ensuring proper error handling

### Implementation Details
The `config_process_cmdline()` function returns an integer status code that was being ignored. The fix captures this return value and propagates it, allowing the caller to detect and handle configuration parsing failures. The X2AP task creation error path now correctly returns -1 instead of continuing execution, preventing the gNB from starting in a partially initialized state.

### Testing
- Verified clean compilation with no warnings about missing return statements
- Confirmed error paths are properly exercised when invalid command-line parameters are provided
- Validated NSA mode gNB initialization correctly handles X2AP task creation failures