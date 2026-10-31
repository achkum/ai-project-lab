"""Finish the legacy slot's current job before restarting it on the new code."""
import argparse,json,subprocess,time
from pathlib import Path
from .job_worker import remote

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--slots',type=int,nargs='+',choices=range(1,5),default=[1])
    parser.add_argument('--wait-all',action='store_true')
    args=parser.parse_args()
    profile=json.loads(Path('config/profile.local.json').read_text())
    runtime=Path(profile['runtime_root'])
    legacy=json.loads((runtime/'legacy-worker-drain.json').read_text())['jobs']
    if args.wait_all:legacy=[j['id'] for j in remote('snapshot')['jobs'] if j['state']=='running']
    report=runtime/('worker-upgrade-result-'+''.join(map(str,args.slots))+'.json')
    restarted=set()
    for _ in range(360):
        try:
            jobs=remote('snapshot')['jobs']
            if not any(j['id'] in legacy and j['state']=='running' for j in jobs):
                for slot in args.slots:
                    if slot in restarted:continue
                    task='ai-lab-job-worker'+('' if slot==1 else '-'+str(slot))
                    subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
                        f"Stop-ScheduledTask -TaskName {task}; "
                        f"for ($attempt=0; $attempt -lt 30 -and (Get-ScheduledTask -TaskName {task}).State -eq 'Running'; $attempt++) {{ Start-Sleep -Milliseconds 200 }}; "
                        f"Start-Sleep -Seconds 1; Start-ScheduledTask -TaskName {task}; Start-Sleep -Seconds 1; "
                        f"if ((Get-ScheduledTask -TaskName {task}).State -ne 'Running') {{ exit 1 }}"],
                        check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                    restarted.add(slot)
                report.write_text(json.dumps({'complete':True,'at':time.time()}))
                return
        except Exception:
            pass
        time.sleep(5)
    report.write_text(json.dumps({'complete':False,'reason':'Workers did not finish within 30 minutes'}))

if __name__=='__main__':main()
