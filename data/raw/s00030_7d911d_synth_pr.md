## Title: Fix thread-unsafe access to interpolation state in LTE DL channel estimation

### Summary
The LTE downlink channel estimation function used a static global variable `interpolateS11S12` to control pilot interpolation logic across OFDM symbols. This variable was read and modified at multiple points without synchronization, creating a race condition when multiple UE processing threads executed concurrently. The shared state could cause non-deterministic interpolation behavior and potential crashes under multi-threaded workloads.

The fix eliminates the global variable by moving the interpolation state to per-thread storage within the UE context structure. Each processing thread now maintains its own `interpolateS11S12` flag, preventing inter-thread interference while preserving the original symbol-to-symbol state tracking logic.

### Changes
- `openair1/PHY/LTE_ESTIMATION/lte_dl_channel_estimation.c`: 
  - Removed static global `interpolateS11S12` declaration
  - Updated all accesses to use per-thread storage: `ue->common_vars.common_vars_rx_data_per_thread[ue->current_thread_id[Ns>>1]].interpolateS11S12`
  - Modified lines: 46 (removed), 561, 570, 631 (updated references)
- `openair1/PHY/defs_UE.h`: Added `int interpolateS11S12` field to the per-thread common variables structure

### Implementation Details
The per-thread variable is indexed by `ue->current_thread_id[Ns>>1]`, ensuring each subframe processing thread maintains independent interpolation state. The lifecycle remains identical to the original implementation: initialized implicitly to 1, set to 1 at symbol 0, and conditionally set to 0 at specific subframe/symbol boundaries.

### Testing
- Verified thread safety through static analysis: no shared mutable state remains in the channel estimation path
- Confirmed functional equivalence by comparing interpolation logic flow before and after changes
- Validated that the fix preserves the original interpolation behavior for both FDD and TDD configurations