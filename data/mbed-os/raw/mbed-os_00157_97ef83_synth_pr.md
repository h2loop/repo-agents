## Title: Add NULL checks for EGU instance in SWI driver to prevent crashes

### Summary
This PR fixes a potential NULL pointer dereference in the nrfx SWI driver. The `nrfx_swi_egu_instance_get()` function can return NULL for certain SWI instances, but this return value was not being checked before passing it to EGU functions like `nrf_egu_int_enable()` and `nrf_egu_int_disable()`. This could lead to crashes or undefined behavior when these functions are called with a NULL pointer.

The issue was identified in three functions within `nrfx_swi.c`:
1. `swi_handler_setup()` - Missing NULL check before calling `nrf_egu_int_enable()`
2. `nrfx_swi_all_free()` - Missing NULL check before calling `nrf_egu_int_disable()`
3. `egu_irq_handler()` - Missing NULL check before using the EGU instance

The fix adds proper NULL checks around EGU function calls, conditional on the compile-time check `(NRFX_SWI_EGU_COUNT < SWI_COUNT)`, matching the existing pattern used in `nrfx_swi_trigger()`.

### Changes
- `targets/TARGET_NORDIC/TARGET_NRF5x/TARGET_SDK_15_0/modules/nrfx/drivers/src/nrfx_swi.c`: 
  - Added NULL check in `swi_handler_setup()` before calling `nrf_egu_int_enable()`
  - Added NULL check in `nrfx_swi_all_free()` before calling `nrf_egu_int_disable()`
  - Added NULL check in `egu_irq_handler()` with early return to prevent NULL dereference

### Testing
Code review and static analysis. The fix follows the existing pattern already used in the same file for similar cases.