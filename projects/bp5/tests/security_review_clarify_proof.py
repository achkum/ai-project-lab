"""Independent clarification race proof; synthetic TestClient accounts/temp DB only."""
import sys, threading, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import test_production as base

class ClarificationReview(base.ProductionTest):
 def test_review_races_and_replay(self):
  for operation in ('reset','delete'):
   account=self.register('review-clarify-'+operation);headers=self.hdr(account['csrf'])
   sid=self.c.post('/api/missions',headers=headers,json={'mission_id':'lib_test_m1','request_id':'start-'+operation}).json()['session']['id']
   miss=self.c.post(f'/api/missions/{sid}/turn',headers=headers,json={'text':'coffee please','request_id':'unmatched'}).json()['session']
   body={'request_id':'review-choice','step_id':'one','intent_id':'coffee','turn_index':1,'turn_id':miss['turns'][1]['turn_id']}
   self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers={**headers,'origin':'https://wrong.example'},json=body).status_code,403)
   gate=threading.Barrier(3);results={};errors=[]
   def run(name):
    try:
     gate.wait(timeout=5)
     if name=='clarify':result=self.c.post(f'/api/missions/{sid}/clarify',headers=headers,json=body)
     elif operation=='reset':result=self.c.post(f'/api/missions/{sid}/reset',headers=headers,json={'request_id':'review-reset'})
     else:result=self.c.delete(f'/api/missions/{sid}',headers=headers)
     results[name]=result.status_code
    except BaseException as exc:errors.append(exc)
   workers=[threading.Thread(target=run,args=(name,)) for name in ('clarify','other')]
   for worker in workers:worker.start()
   gate.wait(timeout=5)
   for worker in workers:worker.join(timeout=10);self.assertFalse(worker.is_alive())
   self.assertFalse(errors,errors);self.assertEqual(results['other'],200)
   final=self.c.get(f'/api/missions/{sid}')
   if operation=='delete':
    self.assertIn(results['clarify'],(200,404));self.assertEqual(final.status_code,404)
    self.assertEqual(self.c.post(f'/api/missions/{sid}/clarify',headers=headers,json=body).status_code,404)
   else:
    self.assertIn(results['clarify'],(200,409));session=final.json()['session'];self.assertEqual(session['current_step'],'one');self.assertEqual(len(session['turns']),1)
    retry=self.c.post(f'/api/missions/{sid}/clarify',headers=headers,json=body)
    self.assertEqual(retry.status_code,200 if results['clarify']==200 else 409)
    session=self.c.get(f'/api/missions/{sid}').json()['session'];self.assertEqual(session['current_step'],'one');self.assertEqual(len(session['turns']),1)
   self.c.post('/api/auth/logout',headers=headers,json={})

if __name__=='__main__':
 suite=unittest.TestSuite([ClarificationReview('test_review_races_and_replay')])
 raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
