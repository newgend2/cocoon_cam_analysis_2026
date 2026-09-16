"""Create full-resolution, metadata-free web copies; verify source checksums."""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
from PIL import Image, ImageOps


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', type=Path, required=True, help='Private JSON list: source URL, sha256')
    p.add_argument('--output', type=Path, default=Path('docs/images'))
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--workers', type=int, default=4)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    def convert(row):
        image_id = row['sha256'][:20]
        target = args.output / (image_id + '.webp')
        try:
            if target.exists():
                with Image.open(target) as im:
                    return dict(id=image_id, available=True, width=im.width, height=im.height, bytes=target.stat().st_size)
            with urlopen(row['url'], timeout=45) as response:
                source = response.read()
            if hashlib.sha256(source).hexdigest() != row['sha256']:
                raise ValueError('Source checksum mismatch')
            with Image.open(io.BytesIO(source)) as original:
                original.load()
                im = ImageOps.exif_transpose(original).convert('RGB')
                # A new pixel-only image cannot carry EXIF, GPS, XMP or comments.
                clean = Image.frombytes('RGB', im.size, im.tobytes())
                clean.save(target, 'WEBP', quality=90, method=4)
                return dict(id=image_id, available=True, width=im.width, height=im.height, bytes=target.stat().st_size)
        except Exception as exc:
            return dict(id=image_id, available=False, error=type(exc).__name__)
    manifest = json.loads(args.manifest.read_text())
    results = []
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        for row in pool.map(convert, manifest):
            results.append(row)
            if len(results) % 100 == 0:
                print(f'Processed {len(results)} / {len(manifest)} images', flush=True)
    args.report.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({'available': sum(r['available'] for r in results), 'total': len(results),
                      'bytes': sum(r.get('bytes', 0) for r in results)}))


if __name__ == '__main__':
    main()
