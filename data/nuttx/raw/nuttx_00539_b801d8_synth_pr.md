## Title: Add NULL pointer checks in blkoutstream functions to prevent dereference errors

### Summary
This PR addresses potential NULL pointer dereferences in the block output stream implementation (`lib_blkoutstream.c`). While `lib_blkoutstream_close` properly checks for NULL pointers, several internal functions (`blkoutstream_flush`, `blkoutstream_seek`, `blkoutstream_puts`) directly dereference `stream->inode`, `stream->cache`, and `inode->u.i_bops` without prior validation. These unchecked accesses could lead to crashes if the stream is partially initialized or if underlying block operations are unavailable.

The changes add defensive NULL checks before each pointer dereference, returning `-EIO` when critical components are missing. This improves robustness during error conditions or abnormal usage patterns without affecting normal operation.

### Changes
- `libs/libc/stream/lib_blkoutstream.c`: Added NULL pointer checks in `blkoutstream_flush`, `blkoutstream_seek`, and `blkoutstream_puts` before accessing `stream->inode`, `stream->cache`, or block driver operations.

### Testing
- Code review confirms all critical pointers are now checked before use.
- No functional changes to normal execution paths; error handling improved.