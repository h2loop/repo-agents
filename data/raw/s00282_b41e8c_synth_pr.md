## Title: Fix incorrect assertion message in UE context modification refuse handler

### Summary
Correct a copy-paste error in an AssertFatal message within the F1AP UE context modification refuse handler. The assertion checks for the presence of CriticalityDiagnostics IE (which is not implemented), but the error message incorrectly referenced "DRBs Modified List". This fix updates the message to accurately reflect what the code is validating, preventing developer confusion during debugging and failure analysis.

### Changes
- `openair2/F1AP/f1ap_du_ue_context_management.c`: Updated AssertFatal message at line 1671 from "handling of DRBs Modified List not implemented" to "handling of CriticalityDiagnostics not implemented" to match the actual IE being checked.

### Testing
- Verified clean compilation of the F1AP subsystem
- Code review confirms the assertion context matches the corrected message text