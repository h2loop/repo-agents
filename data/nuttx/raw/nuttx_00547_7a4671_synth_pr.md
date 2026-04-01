## Title: Fix Missing Interrupt Clear in kinetis_detach

### Summary
This PR addresses a potential interrupt handling issue in the Kinetis LPUART driver's `kinetis_detach` function. Previously, when detaching interrupts during serial port shutdown, the driver would disable the interrupt but not clear any pending interrupts that might still be active. This could lead to spurious interrupt triggers or system instability in certain conditions.

The fix adds a call to `kinetis_clrpend()` to clear any pending interrupts on the LPUART IRQ line before detaching from the interrupt handler. This ensures a clean interrupt state transition when closing the serial port.

### Changes
- `arch/arm/src/kinetis/kinetis_lpserial.c`: Added `kinetis_clrpend(priv->irq)` call in `kinetis_detach()` function to clear pending interrupts before irq_detach()

### Rationale
Without clearing pending interrupts during detach, there's a window where stale interrupt conditions could cause unexpected behavior after the interrupt handler has been detached. This is particularly important in real-time embedded systems where interrupt state consistency is critical for system stability.