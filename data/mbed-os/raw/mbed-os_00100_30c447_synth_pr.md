## Title: Fix missing break statement in I2C interrupt handler switch

### Summary
This PR fixes a missing `break` statement in the I2C asynchronous interrupt handler (`i2c_irq_handler_asynch`) for the M2354 target. The omission caused fall-through behavior in the switch statement when handling the 0x50 status case (Master Receive Data ACK), leading to unintended execution of the subsequent 0x40 case (Master Receive Address ACK). This could result in incorrect I2C control register settings and unpredictable behavior during I2C data reception.

The fix adds the missing `break` statement after handling the 0x50 case, ensuring proper control flow isolation between switch cases. This resolves potential I2C communication errors and improves system reliability.

### Changes
- `targets/TARGET_NUVOTON/TARGET_M2354/i2c_api.c`: Added missing `break` statement in `i2c_irq_handler_asynch` function after processing the 0x50 (Master Receive Data ACK) case in the switch statement.

### Testing
- Verified correct I2C functionality through standard I2C communication tests
- Confirmed proper interrupt handling behavior with logic analyzer
- No performance impact observed