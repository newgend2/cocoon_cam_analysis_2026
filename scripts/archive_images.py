"""Copy a source inventory into a content-addressed, checksum-verified archive.

The supplied JSON is private and contains source URLs. Source locations are
read-only. Existing objects are verified before reuse, never overwritten.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    source=json.loads(args.inventory.read_text())
    grouped=defaultdict(list)
    for row in source: grouped[row['sha256']].append(row)
    objects=args.output/'objects'
    objects.mkdir(parents=True,exist_ok=True)
    def copy(item):
        digest, copies=item
        suffix=Path(copies[0]['relative_path']).suffix.lower()
        target=objects/(digest+suffix)
        if not target.exists():
            with urlopen(copies[0]['url'],timeout=90) as response:
                payload=response.read()
            if hashlib.sha256(payload).hexdigest()!=digest:
                raise ValueError('Checksum mismatch: '+digest)
            temp=target.with_suffix('.partial')
            with temp.open('xb') as f:
                f.write(payload);f.flush();os.fsync(f.fileno())
            os.replace(temp,target)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('Archive verification failed: '+digest)
        relative=Path(copies[0]['relative_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe relative filename')
        browse=args.output/'images'/relative
        browse.parent.mkdir(parents=True,exist_ok=True)
        if browse.exists() and hashlib.sha256(browse.read_bytes()).hexdigest()!=digest:
            browse=browse.with_name(browse.stem+'-'+digest[:12]+browse.suffix)
        if not browse.exists():os.link(target,browse)
        return {'sha256':digest,'archive_file':str(target.relative_to(args.output)),
                'browse_file':str(browse.relative_to(args.output)),
                'bytes':target.stat().st_size,'sources':copies}
    results=[]
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        for row in pool.map(copy,grouped.items()):
            results.append(row)
            if len(results)%100==0:print(f'Archived and verified {len(results)}/{len(grouped)}',flush=True)
    (args.output/'manifest.json').write_text(json.dumps(results,indent=2)+'\n')
    (args.output/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['archive_file']+'\n' for r in results))
    summary={'source_files':len(source),'unique_images':len(results),
             'duplicate_source_copies':len(source)-len(results),'bytes':sum(r['bytes'] for r in results)}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
