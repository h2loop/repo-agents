## Title: Fix use-after-free vulnerability in NR UL HARQ process management

### Summary
Fix a use-after-free vulnerability in the NR UL HARQ process handling where HARQ process memory could be freed while still being accessed by the uplink encoding pipeline. The race condition occurred when `nr_ulsch_encoding` was actively using a HARQ process that could be simultaneously released by `free_nr_ue_ul_harq()`, leading to memory corruption and potential crashes.

The vulnerability manifested when uplink scheduling and HARQ cleanup operations overlapped, particularly under high-throughput scenarios with frequent HARQ process reuse. The fix implements reference counting on HARQ processes to ensure safe memory lifecycle management.

### Changes
- **openair1/PHY/NR_UE_TRANSPORT/nr_transport_ue.h**: Added `ref_count` field to `NR_UL_UE_HARQ_t` structure to track active usage
- **openair1/PHY/NR_UE_TRANSPORT/nr_ulsch_coding.c**: 
  - Increment `ref_count` on HARQ process entry in `nr_ulsch_encoding()`
  - Decrement `ref_count` on all exit paths (including error conditions)
  - Ensures process cannot be freed while encoding is in progress
- **openair1/PHY/INIT/nr_init_ue.c**:
  - Initialize `ref_count` to 0 in `nr_init_ul_harq_processes()`
  - Add reference count check in `free_nr_ue_ul_harq()` to skip freeing in-use processes with warning log

### Implementation Details
The reference counting pattern ensures that:
1. Each HARQ process starts with `ref_count = 0` when initialized
2. `nr_ulsch_encoding()` increments the count before accessing process memory
3. All function exit paths properly decrement the count
4. The cleanup function verifies `ref_count == 0` before freeing memory
5. Processes with non-zero reference counts are skipped with a warning log for debugging

This minimal, targeted fix avoids complex locking while preventing the use-after-free condition across all code paths.