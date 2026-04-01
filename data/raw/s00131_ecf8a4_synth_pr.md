## Title: Fix copy-paste error in NAS network simulator attach complete handling

### Summary
The `_process_attach_complete()` function in the NAS network simulator contains a copy-paste error where failure simulation logic was incorrectly placed at the end of the function rather than at the beginning. This static counter-based logic is designed to occasionally inject transmission failures for testing purposes, but its placement meant it would never execute before the main processing path. Additionally, `_process_emm_msg()` was missing proper initialization of the return variable in the default case, potentially causing undefined behavior.

### Changes
- **openair3/NAS/TEST/NETWORK/network_simulator.c**:
  - Moved the static `_attach_complete_failure_counter` declaration and related failure simulation logic (sleep + error injection) to the top of `_process_attach_complete()`, ensuring it executes before message processing as intended
  - Added `bytes = 0;` initialization in the default case of `_process_emm_msg()` to ensure consistent return values when encountering unknown EMM message types

### Implementation Details
The failure simulation mechanism uses a static counter that decrements on each call, randomly sleeping and returning -1 to simulate network transmission failures. This is test infrastructure code meant to validate error handling paths in the NAS stack. The original placement after the main processing logic prevented the simulation from ever triggering, defeating its purpose. The fix restores the intended behavior where failures can be injected at function entry.