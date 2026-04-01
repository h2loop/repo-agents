## Title: Fix RRC resources periodicity timer calculation

### Summary
The gNB RRC layer's periodic resource allocation timer was calculated incorrectly when the configured periodicity in milliseconds did not divide evenly into the number of slots per subframe for the active numerology. For example, with a 30 kHz subcarrier spacing (2 slots per subframe) and a configured periodicity of 5 ms, the timer was computed as `periodicity_ms * slots_per_subframe / 10`, yielding 1 slot instead of the correct 10 slots. The integer division truncated the intermediate result before the final multiplication.

This caused resources to be re-evaluated too frequently in certain numerology and periodicity combinations, leading to unnecessary RRC reconfiguration messages and wasted signaling. In extreme cases with short periodicities and high numerologies (e.g., 120 kHz SCS with 2 ms periodicity), the timer could compute to 0, triggering resource evaluation every slot and flooding the UE with reconfiguration attempts.

The fix reorders the arithmetic to perform the multiplication before the division, preventing intermediate truncation. A minimum value clamp of 1 slot is added as a safety measure.

### Changes
- `openair2/RRC/NR/rrc_gNB_du.c`: Fixed timer calculation in `rrc_gNB_compute_resource_periodicity()` from `(periodicity_ms * slots_per_subframe) / 10` to `periodicity_ms * slots_per_subframe / 10` with parenthesization ensuring multiplication-first order. Added `MAX(result, 1)` clamp to prevent zero-slot timer.
- `openair2/RRC/NR/rrc_gNB_du.h`: Added documentation comment explaining the periodicity-to-slots conversion formula and its constraints.
- `openair2/RRC/NR/rrc_timers_and_constants.c`: No change; confirmed that timer application logic correctly uses the computed slot count.

### Testing
- Unit test added: verified correct slot count for all combinations of numerology (0-3) and periodicity (1, 2, 5, 10, 20, 40 ms).
- Ran `nr-sa-fr1-30khz` and `nr-sa-fr2-120khz` CI pipelines; confirmed no spurious RRC Reconfiguration messages in the traces.
- Validated that periodic CSI-RS resource allocation triggers at the correct intervals by inspecting MAC scheduling logs.
