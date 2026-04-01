## Title: Fix uninitialized memory read in OMG mobility update loop

### Summary
The OMG (OpenAirInterface Mobility Generator) module in `openair2/UTIL/OMG/omg.c` contains a bug where the `update_nodes` function iterates through all mobility types, including SUMO, regardless of whether `SUMO_IF` is defined. When `SUMO_IF` is not defined, the `job_vector[SUMO]` entry remains uninitialized, but the loop still performs a null check on it (`job_vector[i] != NULL`). This reads uninitialized memory, causing undefined behavior that can manifest as sporadic crashes or incorrect mobility updates.

The root cause is that the loop bound `MAX_NUM_MOB_TYPES` includes SUMO, but the conditional compilation logic only protects the SUMO-specific code blocks, not the iteration itself. This fix ensures the SUMO mobility type is skipped entirely during iteration when `SUMO_IF` is not defined, preventing the uninitialized memory access.

### Changes
- **openair2/UTIL/OMG/omg.c**: 
  - Modified `update_nodes()` to add conditional compilation logic that skips the SUMO mobility type when `SUMO_IF` is not defined
  - Updated `set_new_mob_type()` to exclude SUMO from job vector cleanup (changed condition from `prev_mob != STATIC` to `prev_mob != STATIC && prev_mob != SUMO`)

### Implementation Details
The fix uses `#ifdef SUMO_IF` to conditionally compile two code paths:
- When `SUMO_IF` is defined: includes SUMO in the iteration (original behavior)
- When `SUMO_IF` is not defined: explicitly skips the SUMO index using `continue` before accessing `job_vector[i]`

This ensures the uninitialized `job_vector[SUMO]` is never accessed when SUMO support is disabled at compile time.