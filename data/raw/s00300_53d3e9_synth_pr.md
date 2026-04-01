## Title: Fix signed/unsigned integer comparison in NR MAC gNB beam configuration

### Summary
The NR MAC gNB beam initialization code contains a signed/unsigned integer comparison mismatch where `beam_allocation_size` (declared as signed `int`) is compared against unsigned values in size calculations within `initialize_beam_information()`. This triggers compiler warnings and risks incorrect branching behavior. Since these fields represent allocation counts and sizes, they are semantically unsigned.

This patch corrects the type declarations by changing `beams_per_period` and `beam_allocation_size` fields in the `NR_beam_info_t` struct from `int` to `unsigned int`, eliminating the comparison mismatch and aligning the types with their usage.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/nr_mac_gNB.h`: Changed `beams_per_period` and `beam_allocation_size` fields in `NR_beam_info_t` struct from `int` to `unsigned int`

### Testing
- Verified the signed/unsigned comparison warning is eliminated during compilation
- Confirmed beam allocation logic functions correctly with unsigned types
- Validated no regressions in beam management for both NO_BEAM_MODE and beam-enabled configurations