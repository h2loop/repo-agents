## Title: Fix NFAPI CONFIG.request state machine documentation for VNF address TLVs

### Summary
The NFAPI P5 interface contained misleading documentation regarding VNF address TLVs in `pack_nr_config_request()`. The code comment incorrectly stated that p7_vnf_address_ipv4 and p7_vnf_address_ipv6 TLVs were included for both IDLE and CONFIGURED states, which violates 3GPP specification requirements. Per the spec, these TLVs must only be included in CONFIG.request messages when the NFAPI state machine is in IDLE state. This documentation error could lead to incorrect implementations or state machine violations downstream. The fix corrects the comments to clearly indicate these TLVs are IDLE-state-only, ensuring 3GPP compliance and preventing potential interoperability issues during state transitions.

### Changes
- `nfapi/open-nFAPI/fapi/src/nr_fapi_p5.c`: Updated comments around VNF address TLV packing to correctly state "IDLE state only" per 3GPP spec. Added clarifying markers at start and end of the IDLE-state-only TLV block for better code maintainability.

### Testing
- Code review confirms VNF address TLVs are only packed within appropriate state context
- Verified no functional code changes required as implementation already respects state boundaries
- Recommend NFAPI state machine transition tests to validate IDLE→CONFIGURED behavior excludes VNF address TLVs