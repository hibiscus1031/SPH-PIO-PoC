# Stage07C checkpoint selection policy

The sole selected checkpoint minimizes global-balanced FRESH_VALIDATION_V2 Q_def_v2 among updates >=320; earlier update wins ties. TRAIN, consumed validation, LCDF_08, diagnostics, sealed test, and arm comparison cannot participate.
