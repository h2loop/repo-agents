## Title: Fix GPIO Pin Multiplexing Conflicts in SIM Linux GPIO Chip Driver

### Summary
This PR resolves GPIO pin multiplexing conflicts in the SIM Linux GPIO chip driver by implementing proper pin state checking before reconfiguration. Previously, attempting to reconfigure a GPIO pin with the same direction or interrupt settings would cause conflicts and errors. The changes add validation logic to check the current pin configuration using `GPIO_V2_GET_LINEINFO_IOCTL` and avoid unnecessary reconfigurations.

### Changes
- **arch/sim/src/sim/posix/sim_linux_gpiochip.c**: 
  - Added pin direction validation in `host_gpiochip_direction()` to prevent reconfiguration conflicts
  - Implemented interrupt configuration checking in `host_gpiochip_irq_request()` to avoid duplicate setups
  - Enhanced consumer naming for better GPIO line identification

### Why
The SIM architecture's Linux GPIO chip driver was experiencing conflicts when applications attempted to reconfigure GPIO pins that were already in use with the same settings. This caused unnecessary file descriptor closures and reinitializations, leading to potential race conditions and error states. By checking the existing configuration before making changes, we eliminate these conflicts while maintaining functional correctness.

### Testing
Verified through simulation testing that GPIO pins can now be safely reconfigured with the same settings without conflicts. Existing functionality remains unchanged while improving driver robustness.