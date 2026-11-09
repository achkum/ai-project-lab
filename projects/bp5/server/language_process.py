"""Bounded local worker transport. This module is not a release candidate."""
import json, os, signal, subprocess, threading

MAX_REQUEST = 32768
MAX_RESPONSE = 16384

class WorkerError(Exception):
    pass

class WorkerBusy(WorkerError):
    pass

class WorkerSupervisor:
    """One request at a time; timeout kills and reaps the entire worker group."""
    def __init__(self, command, startup, *, timeout=15.0, startup_timeout=30.0):
        if not isinstance(command,list) or not command or any(not isinstance(x,str) or not x for x in command):
            raise ValueError('Invalid worker command')
        if not 0 < timeout <= 120 or not 0 < startup_timeout <= 120:
            raise ValueError('Invalid worker deadline')
        self.command=list(command);self.startup=startup;self.timeout=timeout;self.startup_timeout=startup_timeout
        self._lock=threading.Lock();self._proc=None;self._broken=False;self._seq=0;self._initialized=False

    def _stop(self):
        p=self._proc;self._initialized=False
        if not p:return
        tree_uncertain=False
        try:
            if os.name=='nt':
                system_root=os.environ.get('SystemRoot',r'C:\Windows')
                taskkill=os.path.join(system_root,'System32','taskkill.exe')
                try:
                    result=subprocess.run([taskkill,'/PID',str(p.pid),'/T','/F'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
                    tree_uncertain=result.returncode!=0 and p.poll() is None
                except (OSError,subprocess.TimeoutExpired):tree_uncertain=True
                if tree_uncertain:p.kill()
            else:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        except OSError as exc:
            self._broken=True
            raise WorkerError('Worker termination failed') from exc
        finally:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Keep the handle so close() can retry cleanup. A replacement
                # must never be started while this worker might still exist.
                self._broken=True
                raise WorkerError('Worker could not be reaped')
            self._proc=None
            for pipe in (p.stdin,p.stdout):
                try:pipe.close()
                except (OSError,AttributeError):pass
        if tree_uncertain:
            self._broken=True
            raise WorkerError('Worker process tree termination was not verified')

    def _exchange(self, obj, deadline):
        try:data=json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')+b'\n'
        except (TypeError,ValueError) as exc:raise WorkerError('Invalid worker request') from exc
        if len(data)>MAX_REQUEST:raise WorkerError('Worker request too large')
        p=self._proc;result=[]
        def io():
            try:
                p.stdin.write(data);p.stdin.flush();buf=bytearray()
                while len(buf)<=MAX_RESPONSE:
                    part=os.read(p.stdout.fileno(),min(1024,MAX_RESPONSE+1-len(buf)))
                    if not part:raise WorkerError('Worker disconnected')
                    buf.extend(part)
                    if b'\n' in buf:
                        line,extra=bytes(buf).split(b'\n',1)
                        if extra:raise WorkerError('Invalid worker protocol')
                        result.append(json.loads(line.decode('utf8')));return
                raise WorkerError('Worker response too large')
            except BaseException as exc:result.append(exc)
        t=threading.Thread(target=io,daemon=True);t.start();t.join(deadline)
        if t.is_alive():
            try:self._stop()
            finally:
                t.join(5)
                if t.is_alive():self._broken=True
            raise WorkerError('Worker deadline exceeded')
        if not result or isinstance(result[0],BaseException):
            self._stop();raise WorkerError('Worker protocol failed')
        if not isinstance(result[0],dict):self._stop();raise WorkerError('Invalid worker response')
        return result[0]

    def _ensure(self):
        if self._broken:raise WorkerError('Worker unavailable')
        if self._proc and self._proc.poll() is None:return
        if self._proc:self._stop()
        kwargs={'stdin':subprocess.PIPE,'stdout':subprocess.PIPE,'stderr':subprocess.DEVNULL,'bufsize':0,'shell':False}
        if os.name=='nt':kwargs['creationflags']=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
        else:kwargs['start_new_session']=True
        try:self._proc=subprocess.Popen(self.command,**kwargs)
        except OSError as exc:raise WorkerError('Worker unavailable') from exc
        try:reply=self._exchange({'op':'init','config':self.startup},self.startup_timeout)
        except WorkerError:
            self._stop();raise
        if reply!={'ready':True,'protocol':1}:
            self._stop();raise WorkerError('Worker initialization failed')
        self._initialized=True

    def ready(self):
        if not self._lock.acquire(blocking=False):
            # Busy is a capacity condition, not a failed model. The request's
            # deadline still kills a stalled worker; initialization is separate.
            proc=self._proc
            return bool(self._initialized and not self._broken and proc and proc.poll() is None)
        try:self._ensure();return True
        except WorkerError:return False
        finally:self._lock.release()

    def request(self, obj):
        if not self._lock.acquire(blocking=False):raise WorkerBusy('Worker busy')
        try:
            if not isinstance(obj,dict) or 'seq' in obj:raise WorkerError('Invalid worker request')
            self._ensure();self._seq+=1;seq=self._seq
            response=self._exchange({**obj,'seq':seq},self.timeout)
            if type(response.get('seq')) is not int or response['seq']!=seq:
                self._stop();raise WorkerError('Invalid worker response')
            return {key:value for key,value in response.items() if key!='seq'}
        finally:self._lock.release()

    def close(self):
        if not self._lock.acquire(blocking=False):raise WorkerBusy('Worker busy')
        try:self._stop()
        finally:self._lock.release()
