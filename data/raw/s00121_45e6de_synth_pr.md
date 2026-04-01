## Title: Fix memory leak in PDCCH testbench main function

### Summary
The PDCCH testbench (`pdcch_test.c`) allocates three heap structures at the start of `main()`: `PHY_config`, `PHY_vars`, and `mac_xface`. These resources were never freed before program exit, causing a memory leak that triggers static analysis tools and memory checkers like Valgrind. While the leak is small and occurs only once per process invocation, it violates proper resource management principles and can mask genuine memory issues in CI pipelines.

This fix adds a cleanup section at the end of `main()` that frees all allocated structures before returning. Each pointer is checked for NULL before freeing to ensure safety, and pointers are nullified after freeing to prevent use-after-free bugs in future code modifications.

### Changes
- `openair1/PHY/CODING/TESTBENCH/pdcch_test.c`: Added cleanup section before final return statement in `main()` that frees `PHY_vars`, `PHY_config`, and `mac_x