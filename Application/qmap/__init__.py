"""Q-MAP: Quantitative Market Analytics Platform (Stage 2 foundation)."""

__version__ = "0.1.0"

# Bump this whenever standardisation or validation logic changes in a way that
# could change the result for the same raw file and the same source profile.
# It is part of every processing version, so reprocessing stays traceable.
CLEANING_CODE_VERSION = "c2"  # c2 (03-Nov-26, DQ-10): exact duplicates removed, conflicting observations kept
