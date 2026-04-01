## Title: Fix memory leak in UCI PUCCH format 2/3/4 unpacking

### Summary
The `unpack_nr_uci_pucch_2_3_4()` function in the nFAPI P7 interface allocates dynamic memory for SR, HARQ, CSI-part1, and CSI-part2 payload fields. When `pullarray8()` fails to read these fields from the message buffer, the function returns early without deallocating the previously allocated memory, causing memory leaks during parsing errors.

This fix ensures proper cleanup by calling `nfapi_p7_deallocate()` and nullifying the pointer before each early return on error paths. This prevents resource exhaustion during sustained operation when encountering malformed or truncated UCI PUCCH format 2/3/4 messages.

### Changes
- `nfapi/open-nFAPI/nfapi/src/nfapi_p7.c`: Added `nfapi_p7_deallocate()` calls for `sr_payload`, `harq_payload`, `csi_part1_payload`, and `csi_part2_payload` before error returns in `unpack_nr_uci_pucch_2_3_4()`.

### Implementation Details
The cleanup follows the established pattern in the codebase: deallocate the resource, set the pointer to NULL, then return 0. This ensures the memory manager can properly track and reclaim resources even when parsing fails mid-operation.

### Testing
This is a defensive programming fix for error handling paths. The changes are validated by code inspection to ensure all allocated resources are properly cleaned up on failure, matching the resource management patterns used elsewhere in the nFAPI implementation.