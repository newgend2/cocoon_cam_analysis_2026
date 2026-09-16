"""Fail closed on sensitive strings, unsafe assets and oversized public builds."""
import argparse
import json
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.py','.js','.html','.css','.csv','.json','.svg','.md','.txt','.yml','.yaml'}
PATTERNS = {
    'absolute user or mounted path': re.compile(r'(?:/(?:Users|home|media|mnt|Volumes)/[^\s"<>]+|[A-Za-z]:\\(?:Users|ProgramData)\\)', re.I),
    'private-network URL': re.compile(r'https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)(?=[:/\s"\'])',re.I),
    'private key': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'token': re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{35,})'),
    'credential assignment': re.compile(r'(?:password|access_token|client_secret)\s*[=:]\s*["\'][^"\']{6,}',re.I),
}


def webp_chunks(path):
    data=path.read_bytes()
    assert data[:4]==b'RIFF' and data[8:12]==b'WEBP', 'Invalid WebP'
    pos=12;chunks=[]
    while pos+8<=len(data):
        kind=data[pos:pos+4];size=struct.unpack('<I',data[pos+4:pos+8])[0]
        chunks.append(kind);pos+=8+size+(size%2)
    assert pos==len(data), 'Invalid WebP chunk sizes'
    return chunks


def audit(root, denylist=()):
    problems=[]
    files=[p for area in ['docs','scripts','tests'] for p in (root/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [root/n for n in ['README.md','AGENTS.md','requirements.txt','.gitignore'] if (root/n).exists()]
    for p in files:
        relative=p.relative_to(root)
        if relative.parts[0]=='docs' and p.suffix=='.csv' and relative.as_posix()!='docs/downloads/master_capture_history.csv':
            problems.append(f'{relative}: only the master CSV may be published')
        if p.is_symlink(): problems.append(f'{relative}: symbolic link');continue
        if p.suffix=='.webp':
            try:
                if set(webp_chunks(p)) - {b'VP8 ',b'VP8L',b'VP8X',b'ALPH'}:
                    problems.append(f'{relative}: unexpected metadata chunk')
            except AssertionError: problems.append(f'{relative}: invalid WebP')
        elif p.suffix in TEXT_SUFFIXES or p.name in {'.gitignore','.nojekyll'}:
            text=p.read_text()
            for label,pattern in PATTERNS.items():
                # Development documentation may describe a local server. The
                # served site must never connect to one.
                if label=='private-network URL' and relative.parts[0]!='docs':continue
                if pattern.search(text):problems.append(f'{relative}: {label}')
            for term in denylist:
                if term.lower() in text.lower():problems.append(f'{relative}: private denylist match')
        elif p.suffix=='.png':
            from PIL import Image
            with Image.open(p) as im:
                if set(im.info)-{'Software','dpi'}:problems.append(f'{relative}: unexpected PNG metadata')
        else:problems.append(f'{relative}: unexpected file type')
    size=sum(p.stat().st_size for p in (root/'docs').rglob('*') if p.is_file())
    if size>=1_000_000_000:problems.append('Site exceeds 1 GB')
    tracked=subprocess.run(['git','ls-files','-z'],cwd=root,capture_output=True,text=True,check=True).stdout.split('\0')
    allowed_roots={'docs','scripts','tests','.github'}
    allowed_files={'README.md','AGENTS.md','requirements.txt','.gitignore'}
    for name in filter(None,tracked):
        if name.split('/')[0] not in allowed_roots and name not in allowed_files:problems.append('Unexpected tracked file: '+name)
    return {'files_checked':len(files),'site_bytes':size,'problems':problems}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--denylist',type=Path)
    args=p.parse_args();denied=json.loads(args.denylist.read_text()) if args.denylist else []
    result=audit(ROOT,denied);print(json.dumps(result,indent=2));raise SystemExit(bool(result['problems']))
