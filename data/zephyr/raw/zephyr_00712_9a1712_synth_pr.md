## Title: Add timeout handling to phase calculation loop in LiteX clock driver

### Summary
This PR addresses a potential infinite loop in the `litex_clk_calc_phase_normal` function that could occur during phase configuration calculation. The loop iterates through delay and phase multiplier values to find an optimal configuration, but lacked a timeout mechanism to prevent indefinite execution. Under certain phase configurations, this could lead to the system hanging during clock initialization or reconfiguration.

The fix introduces a bounded iteration counter that limits the search to a maximum of `(DELAY_TIME_MAX + 1) * (PHASE_MUX_MAX + 1)` iterations. If this limit is exceeded, the function logs an error and returns `-ETIME`, allowing the system to handle the failure gracefully rather than hanging indefinitely.

### Changes
- `drivers/clock_control/clock_control_litex.c`: 
  - Added `iterations` counter and `max_iterations` constant to `litex_clk_calc_phase_normal`
  - Implemented timeout check within the nested loop that searches for phase configuration
  - Added error logging and early return (`-ETIME`) when timeout is exceeded

### Testing
- Verified the fix compiles correctly with existing build infrastructure
- Confirmed that normal phase calculations complete within the iteration limit
- Tested edge cases where phase search space is fully explored without finding a solution, ensuring timeout is properly triggered