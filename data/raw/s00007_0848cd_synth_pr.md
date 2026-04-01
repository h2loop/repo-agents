## Title: Fix unreachable code in LTE eNB I0 measurements due to extraneous closing brace

### Summary
An extraneous closing brace in the `lte_eNB_I0_measurements` function caused downstream code to be unreachable, preventing proper noise power calculations and RB processing. The misplaced brace at line 100 prematurely closed a conditional block, making all subsequent code—including critical noise floor initialization and RB loop iterations—inaccessible during execution. This likely led to incorrect I0 interference measurements and potential miscalculations of total noise power across resource blocks.

The fix removes the spurious closing brace, restoring the intended control flow where noise power initialization and RB-level calculations execute unconditionally after the conditional block. This ensures proper measurement behavior across all eNB configurations.

### Changes
- `openair1/PHY/LTE_ESTIMATION/lte_eNB_measurements.c`: Removed extraneous closing brace `}` at line 100 that was causing unreachable code path. The brace incorrectly terminated the conditional block early, preventing execution of `n0_power_tot2` initialization and the RB counting loop that follows.

### Implementation Details
The function structure contains a conditional block for updating `n0_power_tot_dBm`. The extra brace after this block was syntactically valid but semantically incorrect, creating a dead code region. No other changes were needed as the remaining code properly belongs in the main function body and should execute regardless of the conditional path taken.

### Testing
- Verified compilation succeeds without warnings for unreachable code
- Reviewed control flow to confirm RB processing loop now executes as intended
- Validated that noise power calculations are properly initialized before RB iterations