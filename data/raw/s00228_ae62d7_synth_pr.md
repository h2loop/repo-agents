## Title: Add NULL check for pusch_Config before compute_precoding_information

### Summary
The NR MAC gNB scheduler was missing a NULL pointer validation for `pusch_Config` before calling `compute_precoding_information()` in the uplink DCI configuration path. When `pusch_Config` is NULL (e.g., during initial configuration or reconfiguration phases), the code would dereference a NULL pointer, leading to undefined behavior and potential crashes.

This patch adds a defensive NULL check before invoking `compute_precoding_information()` to ensure we only compute precoding information when a valid PUSCH configuration is present. This follows the same pattern used elsewhere in the codebase where `pusch_Config` is conditionally accessed.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c`: Added NULL pointer validation for `pusch_Config` before calling `compute_precoding_information()` in the `config_uldci()` function.

### Implementation Details
The fix wraps the `compute_precoding_information()` call with an `if (pusch_Config)` guard. This is consistent with the existing code pattern in the same function where `pusch_Config` is already checked before accessing its fields. The function safely skips precoding information computation when no PUSCH configuration is available, which is the correct behavior for this optional configuration scenario.

This is a minimal, targeted fix that addresses the immediate NULL dereference risk without changing the overall logic flow or message processing semantics.