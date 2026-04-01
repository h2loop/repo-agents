## Title: Fix thread-safety issues in LTE UE measurements accessors

### Summary
The LTE UE measurement accessor functions perform unsynchronized reads from shared PHY variables structures (`PHY_vars_UE_g`), creating race conditions when multiple threads access measurement data concurrently. Functions like `get_PL()`, `get_RSRQ()`, `get_n_adj_cells()`, and `get_rx_total_gain_dB()` read fields from `ue->measurements` and related structures without acquiring proper locks, leading to potential data corruption and undefined behavior in multi-threaded UE operation.

This fix adds proper synchronization by acquiring the existing per-UE `mutex_rxtx` before accessing any shared measurement data. Each accessor now locks the mutex, reads required values into local variables, unlocks the mutex, and returns the cached value. This ensures thread-safe access to shared PHY state while maintaining the existing API contract and minimizing critical section duration.

### Changes
- `openair1/PHY/LTE_ESTIMATION/lte_ue_measurements.c`: Added mutex lock/unlock pairs in `get_PL()`, `get_n_adj_cells()`, `get_rx_total_gain_dB()`, `get_RSRQ()`, and other measurement accessor functions to protect concurrent access to shared `ue->measurements` and `ue->frame_parms` structures.

### Implementation Details
The fix leverages the existing `ue->mutex_rxtx` mutex already used for RX/TX processing synchronization. Each function follows the pattern: lock mutex, read shared state into local variable, unlock mutex, return local variable. This avoids deadlock risks and maintains consistent locking discipline across the codebase.

### Testing
- Verified compilation with pthread support
- Confirmed all code paths properly unlock mutex before returning
- No functional changes to measurement values or API signatures