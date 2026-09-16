Cocoon cam · Emerald Queen 2026
Published review snapshot: 2026-09-16

Files
published_reviews.csv: all 1,159 original appearance rows plus the saved review
  fields. assigned_tag is the original assignment in this file.
appearance_records_reviewed.csv: all appearances after incorporation of the
  published decisions. assigned_tag is effective; source_assigned_tag is original.
image_records_reviewed.csv: one row per canonical image. image_id and image_file
  identify the public copy; no original filenames or source locations are included.
  image_available=false retains a record whose source image is corrupt.
bee_records_reviewed.csv: one row per effective included tag, with its history.
tagging_recapture_by_date.csv: the 28 capture dates, including recorded dates
  whose included captures total zero after review.
calendar_timeline.csv: all calendar dates between the first and last capture.
  capture_records_present=false means no capture records, not observed absence.
  Daily values are blank for these dates; cumulative identities carry forward.
dataset_summary.json: dataset counts and the SHA-256 of the source review export.

Core fields
appearance_id: YYYY-MM-DD/bee-N, a capture event identifier rather than a bee ID.
capture_date: capture date recorded in the original file metadata.
bee_number: within-day capture number.
assigned_tag: see file-specific definition above.
source_assigned_tag: original tag before review; blank when no single assignment.
reviewed_tag: the reviewer's entered ID, including entries not yet confirmed.
review_status: confirmed, corrected, uncertain, unreadable, duplicate, dorsal,
  or blank (no completed decision). A blank status does not mean the image was
  never viewed. The source contains 27 unconfirmed n8tag appearances.
review_note: saved observation, preserved from the published review.
domain_status: in_domain or outside_domain.
analysis_included: the source pipeline's domain-inclusion flag. Graphs additionally
  require a nonempty effective assigned_tag; true alone is not sufficient.
status/source_status: effective/original metadata-assignment status.
image_count, angles: number of images and view angles for an appearance.
declared_tags, declared_key: original filename tag claims, without the filenames.
decoder_statuses, review_flags, observed_ids: original automated evidence; these
  flags may remain after a manual decision and do not invalidate it automatically.
verification, review_statuses: identity-level summaries inherited from the source
  pipeline. manual_confirmed means at least one appearance was confirmed, not
  that every appearance of the identity received a confirmation.

Timeline definitions
unique_tagged_appearance_count: unique effective included tags on that date.
aruco_captures / n8tag_captures: daily unique tags in each distinct namespace.
new_bees_tagged: identities first observed in the dataset on that date; this is
  not independent proof of the date on which a physical tag was attached.
new_aruco_tags / new_n8tags: first appearances in their respective namespaces.
recaptured_aruco_individuals: ArUco tags already seen on an earlier capture date.
  Multiple bee numbers or angles for the same tag on the same day count once.
  n8tag identities do not contribute to this recapture measure.
cumulative_unique_bees: unique included tag identities observed through that date.

Limits
Outside-domain and unassigned appearances are excluded from timeline counts.
Unconfirmed n8tag assignments remain included in daily and cumulative tag totals.
Same-day reuse is an audit signal, not a recapture. Cross-date tag reuse could
still affect inferred biological identities; these are tag-based records.
The graph and these files describe the published snapshot. Browser-only proposals
are exported separately and do not update the published graph.
Image derivatives retain full pixel dimensions but use lossy WebP compression.
Source originals are preserved separately and are the analysis-quality archive.

Privacy
Tables use explicit approved columns. Machine names, credentials, source paths
and original filenames are absent. Public image files contain no embedded
EXIF, GPS, XMP, ICC profiles or comments.
