## Title: Fix hardcoded C-RNTI in sidelink SDU processing

### Summary
Correct a copy-paste error in `ue_send_sl_sdu()` where a hardcoded test value `0x1234` was incorrectly used as the C-RNTI parameter when calling `mac_rlc_data_ind()`. This bug caused all sidelink SDUs to be tagged with a static C-RNTI instead of the UE's actual assigned C-RNTI, breaking proper UE identification in the RLC layer. This would result in potential data routing failures, dropped sidelink packets, and incorrect association of sidelink traffic to UEs. The hardcoded value was likely left over from debug or development code that wasn't properly updated when the function was repurposed for production sidelink handling.

### Changes
- `openair2/LAYER2/MAC/ue_procedures.c`: Replace hardcoded constant `0x1234` with `UE_mac_inst[module_idP].crnti` in the `mac_rlc_data_ind()` call within `ue_send_sl_sdu()` (line 853).

### Implementation Details
The fix retrieves the correct C-RNTI from the UE's MAC instance context, ensuring each UE's sidelink SDUs are properly identified with their dynamically assigned radio network temporary identifier. This maintains proper separation of sidelink data flows between different UEs and aligns with how the C-RNTI is correctly used in other MAC procedures.

### Testing
- Verified the change compiles successfully in the `oai_nrue` build target
- Code inspection confirms the C-RNTI is now correctly sourced from UE context, matching the pattern used in other MAC data indication calls
- Sidelink functionality should now properly associate SDUs with the correct UE context