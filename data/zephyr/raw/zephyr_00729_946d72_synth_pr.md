## Title: Fix IRQ configuration order in Ethos-U NPU initialization

### Summary
The Ethos-U NPU driver initialized the hardware via `ethosu_init()` before configuring the IRQ handler through `config->irq_config()`. This ordering was problematic because the NPU could generate interrupts during its initialization sequence before the interrupt handler was registered, leading to missed or spurious interrupts that could cause initialization failures or system instability on platforms with aggressive NPU boot sequences.

This fix moves the `config->irq_config()` call to execute before `ethosu_init()`, ensuring the interrupt handler is properly registered before any hardware initialization begins. This guarantees that any interrupts generated during or after NPU initialization are correctly handled by the driver.

### Changes
- `drivers/misc/ethos_u/ethos_u_arm.c`: Moved `config->irq_config()` call from after `ethosu_init()` to before it in `ethosu_zephyr_init()`.

### Testing
- Verified NPU initialization succeeds on Ethos-U65 and Ethos-U55 platforms.
- Confirmed interrupt handling works correctly during NPU boot with interrupt-generating workloads.
- No regression in existing Ethos-U driver test suite.