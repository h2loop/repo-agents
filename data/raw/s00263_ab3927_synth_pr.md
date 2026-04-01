## Title: Fix copy-paste error in PUCCH format 4 configuration

### Summary
The PUCCH format 4 configuration block in `nr_ue_configure_pucch()` incorrectly references `pucch_Config->format3` instead of `pucch_Config->format4` due to a copy-paste error. When the format 4 handling code was duplicated from format 3, the struct member references were not updated, causing the UE to apply format 3 parameters (pi/2-BPSK and additional DMRS flags) to format 4 resources. This leads to incorrect PUCCH transmission configuration and potential protocol compliance issues.

This fix corrects both references to use `format4`, ensuring proper extraction of format-specific parameters from the correct configuration struct.

### Changes
- `openair2/LAYER2/NR_MAC_UE/nr_ue_procedures.c`:
  - Line 1731: Fixed NULL check to use `pucch_Config->format4` instead of `format3`
  - Line 1735: Fixed parameter extraction to use `pucch_Config->format4->choice.setup`

### Testing
- Verified the fix follows the same pattern used correctly in format 1, 2, and 3 handlers
- Code review confirms no other instances of this copy-paste error exist in the function
- Change is isolated to format 4 configuration path with no impact on other PUCCH formats