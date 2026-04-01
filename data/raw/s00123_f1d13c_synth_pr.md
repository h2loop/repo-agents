## Title: Add critical error logging for beam allocation failures in NR MAC scheduler

### Summary
The `beam_allocation_procedure` function in the NR MAC gNB scheduler contains a silent failure path when no beam can be allocated to a UE. The function returns an error-indicating struct `{.new_beam = false, .idx = -1}`, but previously did not log this critical resource exhaustion event. This lack of observability made it difficult to diagnose beam allocation failures during high-traffic periods, initial access problems, and