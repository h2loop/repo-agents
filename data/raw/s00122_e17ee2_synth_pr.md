## Title: Fix signed/unsigned integer comparison mismatches in nFAPI VNF P7

### Summary
The nFAPI VNF P7 subsystem contains signed/unsigned integer comparison mismatches that generate compiler warnings and risk incorrect branching behavior. The `in_sync` field in `nfapi_vnf_p7_connection_info_t` is an unsigned integer type, but multiple functions compare it against signed literals (0 and 1). Additionally, frame/slot number fields (`sfn_sf`, `sfn`, `slot`) in the connection info struct are declared as signed `int` when they should be unsigned `uint16_t` to properly represent their numeric ranges and match their usage patterns.

This fix corrects these type mismatches by: (1) updating struct field types to `uint16_t` for frame/slot counters, and (2) changing comparison literals to unsigned suffixes (`0u`, `1u`) when checking synchronization status. These changes eliminate sign comparison warnings and ensure consistent unsigned arithmetic throughout the synchronization logic without altering functional behavior.

### Changes
- `nfapi/open-nFAPI/vnf/inc/vnf_p7.h`: Change `sfn_sf`, `sfn`, and `slot` fields from `int` to `uint16_t` in `nfapi_vnf_p7_connection_info_t` struct
- `nfapi/open-nFAPI/vnf/src/vnf_p7.c`: Update `in_sync` comparisons to use unsigned literals in `send_mac_slot_indications()`, `send_mac_subframe_indications()`, `vnf_nr_sync()`, `vnf_sync()`, and `vnf_handle_ul_node_sync()`

### Testing
- Verified clean compilation with `-Wsign-compare` flag enabled
- Confirmed no functional regression through VNF initialization and basic synchronization tests
- Static analysis confirms all sign comparison warnings in vnf_p7 module are resolved