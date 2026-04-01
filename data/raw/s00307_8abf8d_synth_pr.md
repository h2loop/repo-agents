## Title: Fix memory leak in CLI configuration structure

### Summary
The CLI subsystem in `openair2/UTIL/CLI` had a memory leak where the `cli_cfg` structure was allocated during initialization but never freed when the CLI session terminated. This caused memory to be leaked on each CLI session lifecycle, which could accumulate in long-running processes or automated test environments that repeatedly create and destroy CLI sessions.

This patch properly frees the allocated `cli_cfg` memory in the cleanup path. Additionally, it refactors the `cli_start()` function to store the pointer returned by `cli_prompt()` in a local variable before using it, improving code clarity and preventing potential use-after-free scenarios.

### Changes
- **`openair2/UTIL/CLI/cli.c`**: 
  - Modified `cli_start()` to capture the `cli_prompt()` return value in `prompt_ptr` before using it in `sprintf()`
  - Added cleanup logic in `cli_finish()` to free `cli_cfg` and set it to NULL when the CLI session ends

### Implementation Details
The fix adds proper resource management to the CLI teardown path. In `cli_finish()`, after logging the logout event, the code now checks if `cli_cfg` is non-NULL, frees the allocated memory, and explicitly sets the pointer to NULL to prevent dangling references. The refactoring in `cli_start()` ensures the dynamically allocated prompt string pointer is explicitly stored before use, making the memory ownership clearer.

### Testing
- Verified CLI commands still function correctly after the changes
- Confirmed no regression in telnet CLI behavior for both gNB and UE softmodem processes
- Memory leak detection tools should now report clean CLI subsystem shutdown