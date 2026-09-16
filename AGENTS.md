# Cocoon cam analysis

This repository is only for the 2026 Emerald Queen hand-net cocoon-cam tag
review, identity records and recapture timeline. Detector training, camera
annotation and statistical model development belong in separate repositories.

- Read README.md and, when present, the ignored LOCAL_CONTEXT.md before work.
- Preserve source reviews and raw images. The published review snapshot is the
  baseline; browser edits are separate proposals until explicitly incorporated.
- Keep ArUco and n8tag namespaces separate. Count recaptures across dates,
  deduplicating repeated appearances of the same tag on the same date.
- Publish only docs/; never add private/ or LOCAL_CONTEXT.md to Git.
- Use explicit export field lists and opaque image identifiers. Do not publish
  source paths, device names, credentials, EXIF or other embedded metadata.
- Before publishing run the data checks, privacy audit and UI checks. Inspect
  staged files and ensure the complete site remains below the hosting size limit.
