## Title: Fix signed/unsigned integer comparison mismatch in pipe I/O functions

### Summary
Correct type mismatches in the `write_pipe()` and `read_pipe()` helper functions to align with POSIX specifications for the `write()` and `read()` system calls. The functions previously used signed `int` types for both the buffer size parameter and return value, while the underlying system calls expect `size_t` (unsigned) for the count parameter and return `ssize_t` (signed). This mismatch could trigger compiler warnings and potential integer conversion issues on platforms where `size_t` differs from `int`.

### Changes
- `common/utils/system.c`: Updated function signatures and local variables in both pipe I/O functions

### Implementation Details
- Changed `size` parameter type from `int` to `size_t` in both `write_pipe()` and `read_pipe()`
- Changed local variable `ret` type from `int` to `ssize_t` to properly capture return values from `write()` and `read()`
- Maintains existing error handling logic (`if (ret <= 0) exit(0)`) which correctly handles the signed return value

### Testing
- Verified compilation succeeds without signed/unsigned comparison warnings
- Changes are isolated to internal helper functions with no external API impact
- Functionality remains identical while improving type safety and POSIX compliance