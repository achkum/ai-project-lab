"""Pin an existing local training checkpoint and original base for offline export.

Run only after training has stopped. This does not validate quality or qualify a
candidate. Output must be a new private file; existing files are never replaced.
"""
import argparse,hashlib,json,os,re,sys
from pathlib import Path
from export_language_fp32 import BASE_REVISION,BASE_MODEL_SHA,TOKENIZER_SHA,REQUIRED

def hash_stable(path):
    if path.is_symlink() or not path.is_file():raise ValueError('Invalid input')
    before=path.stat();h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('Input changed while hashing')
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-dir',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();base=a.base_dir.absolute();checkpoint=a.checkpoint.absolute();output=a.output.absolute()
    if base.is_symlink() or not base.is_dir() or output.exists() or output.is_symlink():raise ValueError('Invalid input or output')
    hashes={name:hash_stable(base/name) for name in sorted(REQUIRED)}
    if hashes['model.safetensors']!=BASE_MODEL_SHA or hashes['tokenizer.json']!=TOKENIZER_SHA:raise ValueError('Original base does not match pinned author revision')
    document={'base_revision':BASE_REVISION,'base_files':hashes,'checkpoint_sha256':hash_stable(checkpoint)}
    with output.open('x',encoding='utf8') as f:json.dump(document,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({'status':'input_hashes_pinned_not_qualified','checkpoint_sha256':document['checkpoint_sha256']}))
if __name__=='__main__':
    try:main()
    except Exception as exc:print('Manifest preparation failed: '+type(exc).__name__,file=sys.stderr);raise SystemExit(1)
