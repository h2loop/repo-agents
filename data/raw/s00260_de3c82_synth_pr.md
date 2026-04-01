## Title: Replace magic number with macro for RRC timer step resolution

### Summary
The RRC timer initialization code used the literal value `10` as a magic number throughout `rrc_timers_and_constants.c` to represent the timer step resolution in milliseconds. This value appeared in numerous `nr_timer_setup()` calls across multiple functions, making the code difficult to maintain and understand. If this resolution ever needed to change, developers would have to manually update dozens of locations, risking inconsistent behavior.

This change introduces a centralized macro `NR_RRC_TIMER_STEP_MS` with the value `10` and replaces all hardcoded instances. This improves code readability, makes the intent explicit, and ensures maintainability by having a single point of definition for the timer step resolution used across all RRC timer configurations.

### Changes
- `openair2/RRC/NR_UE/rrc_timers_and_constants.c`:
  - Added `#define NR_RRC_TIMER_STEP_MS 10` macro definition with descriptive comment
  - Replaced 16+ instances of hardcoded `10` (timer step parameter) with `NR_RRC_TIMER_STEP_MS` in:
    - `init_SI_timers()` - All SIB timer initializations (sib1 through sib14, sib19)
    - `set_rlf_sib1_timers_and_constants()` - T301, T310, T311, N310, N311, T319 timer setups
    - Additional RRC timer setup functions throughout the file

### Implementation Details
- Macro defined at file scope since the timer step resolution is consistent across all RRC timer operations in this module
- No functional changes - the value remains 10ms in all cases, preserving existing behavior
- Original comments indicating "10ms step" were preserved alongside the macro for additional context

### Testing
- Code compiles successfully with no warnings
- No behavioral changes expected since values remain identical
- Recommended: Run RRC connection and reconfiguration tests to verify timer operations remain correct