## Title: Implement proper GTP error indication handling for NGAP interface recovery

### Summary
The Gtpv1uHandleError function previously only logged a generic error message without processing GTP error indication messages, causing NGAP interface handling failures between gNB and AMF. When the GTP-U layer received error indications from the core network, it failed to notify upper layers, leaving NGAP unaware of tunnel failures and preventing proper error recovery procedures from triggering.

This change implements complete GTP error indication processing: message validation, TEID extraction, UE context lookup, and callback notification to upper layers. This allows NGAP to properly handle GTP tunnel failures and execute appropriate recovery actions, resolving downstream procedure failures.

### Changes
- `openair3/ocp-gtpu/gtp_itf.cpp`: Enhanced `Gtpv1uHandleError()` to parse and process GTP error indication messages, perform TEID-to-UE mapping lookups, extract bearer context, and notify upper layers via the registered callback mechanism.

### Implementation Details
- Added robust message validation (length checks and header verification) to reject malformed packets
- Implements mutex-protected access to the global TEID-to-UE mapping table (`globGtp.te2ue_mapping`)
- Constructs proper protocol context with UE ID, bearer ID, and instance information for callback invocation
- Uses zero-length payload in callback to signal error condition to NGAP and other upper layers
- Enhanced logging provides detailed diagnostics including TEID, UE context, and peer address information

### Testing
- Verified error indication messages are correctly parsed and TEID lookup functions properly
- Confirmed callback invocation reaches NGAP layer with correct UE and bearer context
- Validated mutex operations prevent race conditions in multi-threaded gNB environment
- Ensured no regression in normal GTP-U data path operations