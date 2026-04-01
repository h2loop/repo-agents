## Title: Fix GUAMI decoding in NG Setup Response handler

### Summary
The NG Setup Response handler in the gNB NGAP module incorrectly parsed the optional GUAMI list IE returned by the AMF. When the AMF included a ServedGUAMIList with certain optional fields absent (e.g., missing GUAMIType), the decoder attempted to access uninitialized memory, leading to segmentation faults during the NG Setup procedure.

The root cause was a missing presence check before dereferencing the optional GUAMIType pointer within the ServedGUAMIItem. This fix adds a proper NULL check for optional IEs within the GUAMI decoding loop and initializes the local GUAMI structure to safe defaults before populating it. The issue was consistently reproducible when connecting to AMF implementations that omit the optional GUAMIType field, which is permitted by 3GPP TS 38.413.

### Changes
- `openair3/NGAP/ngap_gNB_handlers.c`: Added NULL check for optional GUAMIType IE before dereferencing. Initialize `served_guami` struct to zero before populating fields in the ServedGUAMIList decoding loop.
- `openair3/NGAP/ngap_gNB_management_procedures.c`: Updated `ngap_gNB_compare_guami()` to handle the case where GUAMIType is unset, treating it as the default native type per the spec.
- `openair3/NGAP/ngap_gNB_defs.h`: Added `guami_type_present` boolean flag to the `ngap_guami_t` structure to track whether the optional field was received.

### Testing
- Verified fix against Open5GS and free5GC AMF implementations, both with and without optional GUAMIType present in NG Setup Response.
- Ran the CI `nr-sa-amf-integration` test pipeline; all NGAP-related tests pass.
- Confirmed no regressions in existing `ngap_test` unit tests.
