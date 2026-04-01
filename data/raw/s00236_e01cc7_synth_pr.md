## Title: Fix missing mask initialization in AT+CLAC test command parser

### Summary
The `parse_clac_test()` function in the NAS UE AT command parser fails to initialize the `mask` field of the `at_command` structure. This omission can lead to undefined behavior when the command is processed downstream, as the mask is used to determine command parameter requirements and validation logic. While the action command variant `parse_clac()` correctly sets both `id` and `mask`, the test command parser (`+CLAC=?`) only sets the `id`. This patch ensures the `mask` field is properly initialized to `AT_COMMAND_CLAC_MASK` (defined as `AT_COMMAND_NO_PARAM`), matching the behavior of other AT command parsers and preventing potential NULL pointer dereferences or incorrect command handling.

### Changes
- `openair3/NAS/UE/API/USER/at_command.c`: Added missing `at_command->mask = AT_COMMAND_CLAC_MASK;` initialization in `parse_clac_test()` function at line 1006.

### Implementation Details
The fix aligns with the existing pattern used in the neighboring `parse_clac()` function and follows the standard initialization pattern for all AT command parsers in this file. The `AT_COMMAND_CLAC_MASK` is defined in `at_command.h` as `AT_COMMAND_NO_PARAM`, which correctly reflects that the CLAC test command expects no parameters. This one-line change ensures struct field consistency without affecting normal operation.