## Title: Fix null pointer dereference in LDPC cnProc generator main()

### Summary
The nrLDPC code generator tool (`generator_cnProc`) contains a potential null pointer dereference in its `main()` function. The code accesses `argv[0]` in a `fprintf()` error message without first validating that `argv` and `argv[0]` are non-NULL. While POSIX/C standards guarantee `argc >= 1` and a valid `argv`, defensive programming practices and static analysis tools flag this as unsafe. This patch adds proper NULL checks before dereferencing these pointers.

### Changes
- `openair1/PHY/CODING/nrLDPC_decoder/nrLDPC_tools/generator_cnProc/main.c`: Added NULL validation for `argv` and `argv[0]` in the argument count check. Modified the usage error message to display `"<prog>"` when `argv[0]` is unavailable, preventing the null pointer dereference.

### Implementation Details
The fix extends the existing `argc != 2` condition to also check `argv == NULL || argv[0] == NULL`. When this combined condition is true, the error message uses a generic `"<prog>"` placeholder instead of dereferencing `argv[0]`. This maintains the original error reporting behavior while eliminating the unsafe pointer access.

### Testing
- Verified syntax correctness with `gcc -fsyntax-only`
- The change is minimal and defensive, preserving all existing functionality while preventing crashes in edge-case execution environments