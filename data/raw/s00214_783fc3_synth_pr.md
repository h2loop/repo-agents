## Title: Fix double-free vulnerability in NR UE measurement reporting cleanup

### Summary
The `handle_meas_reporting_remove` function in the NR UE RRC module contained a double-free vulnerability when cleaning up measurement reporting structures. The code unconditionally freed `rrc->MeasReport[id]` without verifying the pointer was valid or clearing it after deallocation. This could cause memory corruption and crashes if measurement reporting was reconfigured multiple times for the same measurement ID, or if the function was called repeatedly during RRC reconfiguration procedures.

This patch prevents the double-free by adding a NULL check before freeing the ASN.1 structure and explicitly nullifying the pointer afterward, ensuring safe cleanup of measurement reporting resources.

### Changes
- `openair2/RRC/NR_UE/rrc_UE.c`: Added NULL pointer validation and post-free NULL assignment in `handle_meas_reporting_remove()` to prevent double-free of measurement report structures.

### Implementation Details
The fix wraps the `asn1cFreeStruc()` call in a conditional block that checks `if (rrc->MeasReport[id])` before freeing. After successful deallocation, the pointer is explicitly set to NULL with `rrc->MeasReport[id] = NULL;`. This follows standard defensive programming practices for preventing use-after-free and double-free bugs in C code managing dynamic memory.