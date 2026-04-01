## Title: Fix uninitialized memory read in is_pattern2_config validation

### Summary
The `is_pattern2_config()` function in the gNB configuration parser was reading uninitialized memory when determining if pattern2 parameters were configured. The function dereferenced `param->i64ptr` without first verifying that the parameter had been set (either explicitly or to its default value), causing undefined behavior when optional configuration parameters were omitted.

This patch adds proper initialization checking before memory dereference. The fix validates the parameter flags using `PARAMFLAG_PARAMSET` and `PARAMFLAG_PARAMSETDEF` to ensure the pointer references valid, initialized memory before reading its value. This prevents spurious pattern2 detection and potential crashes when processing incomplete configuration files.

### Changes
- `openair2/GNB_APP/gnb_config.c`: Refactored `is_pattern2_config()` to add explicit parameter initialization checks. Split the original compound condition into separate validation steps: first checking pointer validity, then verifying parameter initialization flags, and finally checking the value. This ensures safe memory access patterns throughout the configuration parsing path.

### Testing
- Verified with Valgrind that configuration parsing no longer triggers uninitialized memory read warnings
- Confirmed correct behavior when pattern2 configuration is absent (returns false)
- Confirmed correct behavior when pattern2 is explicitly set to -1 (returns false)
- Confirmed correct behavior when pattern2 is set to valid non-negative values (returns true)
- Regression tested with standard gNB configuration files to ensure no functional changes