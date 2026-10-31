import tempfile,unittest,concurrent.futures
from pathlib import Path
from engine.jobs import Jobs

class ParallelJobs(unittest.TestCase):
    def test_concurrent_claims_obey_capacity_without_duplicate_jobs(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'jobs.sqlite'
            cards=[dict(id=f'T{i}',version=1,lane='Thesis',title=f'Topic {i}') for i in range(6)]
            q=Jobs(path,cards,max_parallel=4)
            q.enqueue([dict(id=c['id'],version=1) for c in cards],'parallel-request')
            def claim():
                worker=Jobs(path,cards,max_parallel=4)
                try:return worker.claim()
                finally:worker.close()
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                claimed=[r for r in pool.map(lambda _:claim(),range(6)) if r]
            self.assertEqual(len(claimed),4)
            self.assertEqual(len({r['id'] for r in claimed}),4)
            q.control(claimed[0]['id'],'pause')
            for r in claimed[1:]:q.check(r['id'],r['token'])
            self.assertIsNotNone(q.claim())
            self.assertEqual(q.snapshot()['capacity'],4)
            q.close()
