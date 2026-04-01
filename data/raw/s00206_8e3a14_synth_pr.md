## Title: Fix incorrect parameter type in e1_bearer_context_modif declaration

### Summary
The function declaration for `e1_bearer_context_modif()` in the CU-CP/CU-UP handler used an incorrect parameter type, causing a type mismatch that led to power control errors downstream. Specifically, the function was declared to accept `struct e1ap_bearer_setup_req_s*` instead of the correct `struct e1ap_bearer_mod_req_s*`. This caused the bearer modification request to be incorrectly interpreted as a setup request, resulting in malformed power control parameters and incorrect transmit power levels in the gNB.

The fix corrects the parameter type to match the actual implementation and usage context, ensuring proper parsing of bearer modification messages and correct propagation of power control configuration.

### Changes
- `openair2/LAYER2/nr_pdcp/cucp_cuup_handler.h`: 
  - Changed `e1_bearer_context_modif()` parameter type from `const struct e1ap_bearer_setup_req_s *req` to `const struct e1ap_bearer_mod_req_s *req`
  - Added forward declaration for `struct e1ap_bearer_mod_req_s`

### Implementation Details
The type mismatch caused the compiler to generate incorrect memory layout assumptions when callers passed bearer modification requests to this function. Fields specific to modification requests (including power control parameters) were being read from wrong offsets, leading to garbage values being configured in the lower layers. The corrected signature ensures proper type safety and correct parameter interpretation.

### Testing
- Verified compilation succeeds without type mismatch warnings
- Confirmed bearer modification messages now correctly propagate power control parameters to the MAC/PHY layers
- Validated transmit power levels are within expected range in CU-CP/CU-UP integration tests