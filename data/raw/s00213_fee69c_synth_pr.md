## Title: Fix uninitialized memory read in tracer config module

### Summary
Static variables in the tracer configuration module were implicitly initialized, causing static analyzers to flag potential uninitialized memory reads when `get_local_config()` is called before configuration is loaded. While static variables are zero-initialized by the C standard, explicit initialization ensures deterministic behavior, improves code clarity, and prevents downstream undefined behavior when these values are dereferenced.

### Changes
- `common/utils/T/tracer/config.c`: Explicitly initialize static variables `local`, `local_size`, `remote`, and `remote_size` to `NULL` and `0` respectively (lines 6-9)

### Implementation Details
The `get_local_config()` function returns configuration state by dereferencing the `local` and `local_size` static variables. Without explicit initialization, static analysis tools cannot guarantee these variables are initialized before use. This change makes the initialization explicit and self-documenting, eliminating any ambiguity about initial state.

### Testing
- Verified clean compilation with GCC
- Static analysis scan no longer reports uninitialized memory access warnings for this code path
- Code review confirms all four affected static variables now have explicit initializers