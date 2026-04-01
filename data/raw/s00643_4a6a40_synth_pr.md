## Title: Align max-ldpc-iterations default with 3GPP specification

### Summary
The default value for the `max-ldpc-iterations` parameter in the NR UE softmodem was incorrectly set to 8, which deviates from the 3GPP specification default. This parameter controls the maximum number of LDPC decoding iterations performed during downlink channel decoding. Using a non-compliant default value may result in inconsistent decoding performance and specification compliance issues.

This change updates the default value to 12 iterations to match the 3GPP specification, ensuring proper out-of-the-box behavior without requiring explicit user configuration.

### Changes
- `executables/nr-uesoftmodem.h`: Updated the default value for `max-ldpc-iterations` from `.defuintval=8` to `.defuintval=12` in the `CMDLINE_NRUEPARAMS_DESC` macro definition.

### Implementation Details
The parameter is defined within the command-line parameter descriptor macro that initializes the `nrUE_params` structure. This default value is used when the UE softmodem is started without explicitly setting the `--max-ldpc-iterations` flag. The change is minimal and only affects the out-of-the-box configuration; any explicitly configured values via command line remain unaffected.

### Testing
- Verified the parameter correctly defaults to 12 iterations when no explicit configuration is provided
- Confirmed existing functionality remains unchanged when the parameter is explicitly set via command line
- Validated that the UE softmodem initializes and runs successfully with the new default value