## Title: Increase Default Shell Stack Size and Add Stack Usage Documentation

### Summary
This PR addresses a stack overflow issue in the shell subsystem's `find_completion_candidates` function by increasing the default stack size and adding documentation to help developers configure adequate stack space. The shell completion functionality can consume significant stack memory, especially in applications with complex command structures. The default stack size has been increased from 2048 to 4096 bytes for multithreaded configurations to prevent stack overflow crashes.

### Changes
- **subsys/shell/Kconfig**: Increased default `CONFIG_SHELL_STACK_SIZE` from 2048 to 4096 bytes for multithreading configurations and added documentation about stack usage requirements.
- **include/zephyr/shell/shell.h**: Added documentation note about shell completion stack usage in the API header.
- **subsys/shell/shell.c**: Added code comment in `find_completion_candidates` explaining its stack usage characteristics.

### Why
The shell's command completion feature was causing stack overflows in applications with complex command hierarchies due to insufficient default stack allocation. This change ensures more robust operation out-of-the-box while providing clear guidance for developers to configure appropriate stack sizes based on their application's complexity.

### Affected Files
- `subsys/shell/Kconfig`
- `include/zephyr/shell/shell.h`
- `subsys/shell/shell.c`