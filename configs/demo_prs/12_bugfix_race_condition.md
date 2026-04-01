## Title: Fix race condition in SDAP TUN read thread shutdown

### Summary
The SDAP layer's TUN interface read thread had a race condition during shutdown that caused intermittent crashes in nr-uesoftmodem. The thread performed a blocking `read()` on the TUN file descriptor, and the shutdown path closed the socket from the main thread while the read was still blocked. This produced three failure modes: `read()` returning EBADF and processing the error as data, `read()` returning 0 and entering an infinite retry loop, or the main thread deadlocking on `pthread_join()`.

This fix addresses all three failure modes. The TUN read thread now checks a shared `stop_flag` atomic variable before each `read()` call. The shutdown path sets the flag first, then closes the TUN socket to unblock the read, and finally joins the thread. The read loop explicitly handles `EBADF`, `EINTR`, and `EIO` errno values by exiting cleanly instead of retrying or processing garbage data.

### Changes
- `openair2/SDAP/nr_sdap/nr_sdap.c`: Added `atomic_bool tun_stop_flag` check before each `read()`. Updated errno handling to exit cleanly on `EBADF`, `EINTR`, and `EIO`. Fixed `nr_sdap_stop()` to set the flag, close the TUN fd, then join the thread.
- `openair2/SDAP/nr_sdap/nr_sdap_entity.h`: Added `atomic_bool tun_stop_flag` and `pthread_t tun_read_tid` fields to `nr_sdap_entity_t` for proper shutdown coordination.
- `openair2/SDAP/nr_sdap/nr_sdap_entity.c`: Initialize `tun_stop_flag` to `false` and store the thread ID from `pthread_create()` in `nr_sdap_create_entity()`.

### Testing
- Reproduced the crash by running 100 rapid start/stop cycles of nr-uesoftmodem with rfsimulator; crash rate dropped from ~15% to 0% with the fix.
- Ran the `nr-sa-rfsim-attach-detach-loop` CI test (50 iterations) with ThreadSanitizer enabled; no data race warnings reported in the SDAP module.
- Verified normal data path operation: iperf DL/UL traffic over TUN interface works correctly with no packet loss attributable to the SDAP layer.
