"""Run the isolated probe and bind its receipt to an inspected local OCI image.

Host-side only. Creates no container and changes no service configuration.
"""
import argparse,hashlib,json,re,subprocess,sys


def inspect(container):
    proc=subprocess.run(['docker','inspect',container],capture_output=True,text=True,timeout=30,check=True)
    obj=json.loads(proc.stdout)
    if not isinstance(obj,list) or len(obj)!=1:raise ValueError('Unexpected inspect result')
    return obj[0]


def validate(doc,container,image):
    if doc.get('Id')!=container or doc.get('Image')!=image or not doc.get('State',{}).get('Running'):raise ValueError('Container/image identity mismatch')
    host=doc.get('HostConfig',{})
    if host.get('NetworkMode')!='none' or not host.get('ReadonlyRootfs') or host.get('Privileged') or host.get('PortBindings'):raise ValueError('Unsafe container configuration')
    mounts=doc.get('Mounts',[])
    if not isinstance(mounts,list) or any(m.get('RW') and m.get('Destination')!='/data' for m in mounts):raise ValueError('Unexpected writable mount')
    if sum(1 for m in mounts if m.get('Destination')=='/data' and m.get('RW'))!=1:raise ValueError('Missing isolated data mount')
    return {'container_id':container,'image_id':image,'network_mode':'none','read_only_root':True,
            'mounts':[{'destination':m.get('Destination'),'read_only':not m.get('RW')} for m in mounts]}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--container-id',required=True);p.add_argument('--image-id',required=True);p.add_argument('--expected-memory-bytes',required=True,type=int);a=p.parse_args()
    if not re.fullmatch('[a-f0-9]{64}',a.container_id) or not re.fullmatch('sha256:[a-f0-9]{64}',a.image_id) or not 0<a.expected_memory_bytes<=3*1024**3:raise ValueError('Invalid immutable identity or limit')
    # The token is passed to docker exec using an environment name, not an argv value.
    import os
    if not 24<=len(os.getenv('BP5_STAGING_PROBE_TOKEN',''))<=128:raise ValueError('Staging token required')
    before=validate(inspect(a.container_id),a.container_id,a.image_id)
    cmd=['docker','exec','-e','BP5_STAGING_PROBE=1','-e','BP5_STAGING_PROBE_TOKEN','-e',f'BP5_STAGING_EXPECTED_MEMORY_BYTES={a.expected_memory_bytes}',a.container_id,'python','/app/deploy/language_resource_probe.py']
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=900,check=False)
    after=validate(inspect(a.container_id),a.container_id,a.image_id)
    if before!=after:raise ValueError('Container configuration changed during probe')
    receipt=json.loads(proc.stdout)
    if proc.returncode!=0 or receipt.get('status')!='measurement_complete_not_acceptance' or not receipt.get('worker_native_libraries'):raise ValueError('Probe did not complete')
    encoded=json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()
    print(json.dumps({'status':'image_bound_measurement_not_acceptance','identity':before,'probe_sha256':hashlib.sha256(encoded).hexdigest(),'probe':receipt},sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as exc:print('Identity measurement failed: '+type(exc).__name__,file=sys.stderr);raise SystemExit(1)
