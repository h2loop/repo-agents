## Title: Fix buffer overflow in IRDA HAL receive and transmit interrupt handlers

### Summary
This PR addresses a buffer overflow vulnerability in the STM32F3 IRDA HAL driver's interrupt handlers (`IRDA_Receive_IT` and `IRDA_Transmit_IT`). The issue occurred due to missing bounds checks when reading from or writing to user-provided buffers, potentially allowing out-of-bounds memory access when the transfer count (`RxXferCount`/`TxXferCount`) was improperly managed or corrupted.

The fix adds explicit buffer boundary checks before each data access, ensuring that sufficient space remains in the buffer before writing received data or reading data to transmit. For 9-bit transfers, it verifies at least 2 bytes are available; for 8-bit transfers, at least 1 byte. If insufficient space is detected, the transfer is safely terminated by setting the transfer count to zero.

### Why
Without these checks, a malicious or malformed data stream could cause memory corruption, leading to undefined behavior, crashes, or potential exploitation. This is especially critical in embedded systems where such vulnerabilities can compromise device integrity.

### Affected Files
- `targets/TARGET_STM/TARGET_STM32F3/STM32Cube_FW/STM32F3xx_HAL_Driver/stm32f3xx_hal_irda.c`: Modified `IRDA_Receive_IT` and `IRDA_Transmit_IT` functions to include buffer bounds checking.