## Title: Fix assignment vs equality bug in E1AP bearer context modification parsing

### Summary
Fixed a critical bug in the E1AP bearer context modification request parser where an assignment operator (`=`) was incorrectly used instead of an equality operator (`==`) within a DevAssert statement. This bug, located in `extract_BEARER_CONTEXT_MODIFICATION_REQUEST()`, caused the assertion to always evaluate as true, effectively disabling validation of the `uP_TNL_Information.present` field. This could mask protocol parsing errors where the optional GTP tunnel information structure is present but not properly marked in the ASN.1 presence field, potentially leading to undefined behavior when accessing the `choice.gTPTunnel` union member.

### Changes
- `openair2/E1AP/e1ap.c`: Line 1387 in `extract_BEARER_CONTEXT_MODIFICATION_REQUEST()` - Changed `DevAssert(dl_up_param_in->uP_TNL_Information.present = E1AP_UP_TNL_Information_PR_gTPTunnel)` to use `==` for correct equality comparison, ensuring proper validation of the ASN.1 presence indicator before accessing the GTP tunnel information.

### Testing
- Static code analysis confirms the bug pattern (assignment in boolean context)
- Code review validates the fix correctly implements the intended equality check
- The change is isolated to assertion logic and does not affect runtime behavior when the assertion is disabled in production builds