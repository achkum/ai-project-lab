"""Inventory actual language-runtime binaries inside the candidate image.

Prints only paths, sizes, package versions and hashes; does not inspect learner
or model data and does not create a release manifest.
"""
import hashlib,importlib.metadata,json,os,sys
from pathlib import Path

def record(path):
    p=Path(path).resolve(strict=True)
    if not p.is_file() or p.stat().st_size>1024**3:raise ValueError('Invalid runtime artifact')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return {'path':str(p),'sha256':h.hexdigest(),'bytes':p.stat().st_size}

def main():
    if not sys.platform.startswith('linux'):raise SystemExit('Linux candidate image required')
    import onnxruntime.capi.onnxruntime_pybind11_state as ort_native
    import tokenizers.tokenizers as tok_native
    import numpy.core._multiarray_umath as np_native
    import fasttext_pybind
    paths={'python':sys.executable,'onnxruntime':ort_native.__file__,'tokenizers':tok_native.__file__,'numpy':np_native.__file__,'fasttext':fasttext_pybind.__file__}
    roles={name:record(path) for name,path in paths.items()}
    mapped=set()
    for line in Path('/proc/self/maps').read_text(encoding='utf8').splitlines():
        fields=line.split(None,5)
        if len(fields)==6:
            name=fields[5]
            if name.startswith('/') and '.so' in Path(name).name and Path(name).is_file():mapped.add(str(Path(name).resolve()))
    if len(mapped)>256:raise ValueError('Unexpected runtime mapping count')
    loaded=[record(path) for path in sorted(mapped)]
    versions={name:importlib.metadata.version(name) for name in ('onnxruntime','tokenizers','numpy','fasttext-wheel')}
    print(json.dumps({'platform':sys.platform,'python':sys.version.split()[0],'roles':roles,'loaded_native_libraries':loaded,'versions':versions},indent=2))

if __name__=='__main__':main()
