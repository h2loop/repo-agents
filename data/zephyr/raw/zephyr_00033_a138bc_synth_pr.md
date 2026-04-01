## Title: Add Critical Section Protection to `ull_adv_aux_reset_finalize`

### Summary
This PR addresses a potential race condition in the `ull_adv_aux_reset_finalize` function by adding critical section protection around the `init_reset()` call. The `init_reset()` function manipulates shared state in the auxiliary advertising pool, but the calling function was not protecting this operation with interrupt locking.

The fix uses `arch_irq_lock()`/`arch_irq_unlock()` to ensure atomic execution of the reset initialization, preventing potential corruption of the advertising auxiliary set memory pool during concurrent access.

### Why
The `ull_adv_aux_reset_finalize` function calls `init_reset()` which initializes the auxiliary advertising set memory pool. Without proper synchronization, concurrent access to this shared resource could lead to memory corruption or inconsistent state, particularly during reset operations when interrupts might be scheduled.

### Changes
- `subsys/bluetooth/controller/ll_sw/ull_adv_aux.c`: Added interrupt locking around the `init_reset()` call in `ull_adv_aux_reset_finalize()` to protect the critical section.

### Testing
The change follows the same pattern used elsewhere in the ULL subsystem for protecting critical sections during reset operations. The fix is minimal and maintains existing functionality while adding necessary synchronization.