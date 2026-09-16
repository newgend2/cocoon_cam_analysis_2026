# Cocoon cam analysis · Emerald Queen 2026

The dedicated repository for hand-netted bumble bee tag review and capture
timelines. This project is separate from detector training and camera annotation.

## Published site

The static website is in `docs/`. GitHub Pages publishes that folder from `main`.
It needs no login, laboratory connection, application server or third-party CDN.
Open **Image review** to filter by capture date, initially unidentified tags,
changed assignments, outside-domain records, or other review categories.
**Timeline & downloads** contains the graphs and the single collaborator CSV,
`master_capture_history.csv`. It has one row per included tag, with `tag_id`,
`first_assignment_date`, `recaptured` (true/false), and `recapture_1_date`,
`recapture_2_date`, etc. Dates use YYYY-MM-DD; absent recaptures are blank.
IDs retain the `aruco:` or `n8tag:` prefix. The first assignment date is the
first recorded appearance, not an independently verified tag application date.
Recaptures follow the ArUco-only rules below. Review decisions are not CSV fields.

The published dataset is the 16 September 2026 review snapshot: 1,159 appearances,
1,543 image records, 1,130 completed decisions, 995 effective tag identities, and
143 later-date ArUco recapture events. The 27 unconfirmed n8tag appearances
remain included in capture totals. Ten outside-domain appearances and six
in-domain appearances without an effective identity are excluded from graph counts.

The original image for one reviewed appearance is corrupt; its record and
review are retained with an unavailable-image message. The other 1,542 images
are available as full-resolution WebP derivatives. Web copies use quality 90
compression and contain no EXIF, GPS, XMP, image comments or original filenames.
Use the preserved originals for pixel-level measurements and decoder validation.

## Review persistence

Every visitor starts with the published review decisions. New edits are stored
only in that browser, under a site-specific key. There is no shared write API.
The published reviews and timeline are not changed by a visitor's edits. Browser
storage is not a durable research archive. The public site offers only the master
analysis CSV. A rebuild also generates an internal reviewer under
`private/analysis_exports/viewer/`, with the review-backup button available there.
Serve that directory locally to export saved proposals, including excluded
records. Unsaved form fields are not exported. Browser storage is tied to its
origin and URL path; local and public reviewer proposals are separate.

## Analysis rules

- An appearance is a capture date plus a bee number. Multiple angles are images
  of that appearance, not additional identities.
- Keep `aruco:<id>` and `n8tag:<id>` distinct. A tag identity is not independently
  verified biological identity, particularly where tag reuse is flagged.
- Deduplicate each tag within a date. An ArUco tag seen on a later date is one
  recapture event for that later date. n8tags do not contribute recaptures.
- Preserve original assignments, reviewed assignments, inclusion flags and
  unresolved outcomes. Automated decoder disagreements are evidence only.
- Every calendar date is labeled on the graph. Unsampled dates are shaded and
  their daily counts are blank in `calendar_timeline.csv`, distinct from zero.
- Each daily bar plot includes its cumulative total on a labeled right axis.
  The recapture interval plot measures calendar days from a tag's first recorded
  appearance to each later capture date. Its overall mean weights all recapture
  events equally, including multiple later dates for the same tag. It excludes
  tags never recaptured; the first recorded date is a proxy for initial tagging.
  Event intervals, plotted frequencies and all detailed exports are retained
  internally in `private/analysis_exports/`, outside the published site.

## Repository boundary

- `docs/`: the public viewer, metadata-free images, graphs and master CSV.
- `scripts/`: portable archive, export, graph and audit commands.
- `tests/`: checks on review preservation, capture rules and export privacy.
- `private/` (ignored): unchanged legacy archive, private source inventory,
  master image archive, detailed analysis exports, internal reviewer, source
  mappings and local working tools. Retired public downloads are preserved
  byte-for-byte in `private/analysis_exports/retired_public_exports/`.
- `LOCAL_CONTEXT.md` (ignored): machine-specific access paths and handoff notes.

Never commit private inputs or machine-specific configuration. Raw sources are
read-only. The local master archive stores each unique image byte-for-byte and
maps every original source copy in its private manifest, including legacy dates
that are not part of the 2026 analysis.

## Rebuild and verify

Use Python 3.10+ and install `requirements.txt` in a virtual environment.

```sh
python scripts/archive_images.py --inventory PRIVATE_INVENTORY.json --output PRIVATE_ARCHIVE
python scripts/prepare_images.py --manifest PRIVATE_IMAGE_MANIFEST.json --report PRIVATE_IMAGE_REPORT.json
python scripts/build_public.py --source PRIVATE_REVIEW_SNAPSHOT
python -m unittest discover -s tests
python scripts/audit_public.py
python -m http.server 8765 --directory docs --bind 127.0.0.1
```

The private inventory records source URLs, checksums, relative filenames and
source provenance. The derivative manifest requires only `url` and `sha256`.
Both copying commands verify source bytes against SHA-256 before accepting them.
The public builder uses explicit field lists and checks that the reconstructed
daily totals match the archived timeline. Incorporating new reviews requires a
deliberate updated snapshot and a review of changed identities and totals.
The internal output defaults to `private/analysis_exports/`; override it with
`--internal-output` only to another non-public location. The tests check both the
public contract and internal tables after a local rebuild. Checks that need
private exports are skipped in a public-only checkout.

For the internal reviewer with review-backup export, run a local server:

```sh
python -m http.server 8766 --directory private/analysis_exports/viewer --bind 127.0.0.1
```

Before publishing, audit every tracked file and image metadata, inspect the Git
diff, run data checks, and verify the viewer at its repository subpath. Only the
`docs/` folder is served. No credentials are needed by the website.
