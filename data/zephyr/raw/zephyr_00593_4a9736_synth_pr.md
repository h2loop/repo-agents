## Title: Fix Interrupt Race Condition in LMP90xxx ADC SPI Transactions

### Summary
This patch resolves a potential interrupt race condition in the LMP90xxx ADC driver that could cause system hangs during SPI register access. The issue occurred when the DRDYB (data ready) interrupt fired during SPI transactions, leading to a priority inversion where the interrupt handler attempted to access the same SPI bus resources as the interrupted context. This created a deadlock scenario as the interrupt handler waited for a semaphore already held by the lower-priority thread.

The fix implements interrupt locking around all SPI register read/write operations (`lmp90xxx_read_reg` and `lmp90xxx_write_reg` functions) to prevent the DRDYB interrupt from preempting SPI transactions. This ensures atomic access to the SPI bus during register operations while maintaining proper interrupt latency for other system operations.

### Changes
- `drivers/adc/adc_lmp90xxx.c`: 
  - Added interrupt locking mechanisms to `lmp90xxx_read_reg()` and `lmp90xxx_write_reg()` functions
  - Introduced `irq_lock()/irq_unlock()` calls around SPI transaction blocks
  - Added necessary `unsigned int key` variable declarations for interrupt state preservation

### Testing
Verified fix resolves intermittent hangs during ADC sampling operations on STM32 platforms. Driver now operates reliably under high interrupt load conditions while maintaining expected ADC performance and data integrity.