"""Integration checks for all authored mission examples and terminal paths."""
import unittest, json, hashlib, importlib.util
from pathlib import Path
import production_store as st

class LibraryIntegration(unittest.TestCase):
 def test_complete_library_and_every_path(self):
  lib=json.loads((Path(__file__).resolve().parent.parent/'content'/'library.json').read_text(encoding='utf-8'));situations=lib['situations'];self.assertGreaterEqual(len(situations),18)
  missions=[m for situation in situations for m in situation['missions']];self.assertGreaterEqual(len(missions),54);self.assertTrue(st.library_ready(lib))
  for mission in missions:
   steps={s['id']:s for s in mission['steps']};required=set(mission['completion_objectives']);terminal=[0];visited=set()
   def walk(step_id,found,seen):
    key=(step_id,tuple(sorted(found)));self.assertNotIn(key,seen,(mission['id'],'cycle',step_id));visited.add(step_id);step=steps[step_id];found=found|{step['objective']};seen=seen|{key}
    for intent in step['intents']:
     self.assertTrue(intent.get('examples_sv'),(mission['id'],step_id,intent['id']))
     for example in intent['examples_sv']:
      matched=st.match_step(step,example);self.assertIsNotNone(matched,(mission['id'],step_id,example));self.assertEqual(matched['id'],intent['id'])
     next_step=intent['next_step']
     if next_step is None:terminal[0]+=1;self.assertTrue(required.issubset(found),(mission['id'],'incomplete terminal',required-found))
     else:self.assertIn(next_step,steps);walk(next_step,found,seen)
   walk(mission['start_step'],set(),set());self.assertGreater(terminal[0],0,mission['id']);self.assertEqual(visited,set(steps),(mission['id'],'unreachable steps'))
 def test_separately_authored_regressions(self):
  root=Path(__file__).resolve().parent.parent/'content';lib=json.loads((root/'library.json').read_text(encoding='utf-8'));cases=json.loads((root/'library_evaluation.json').read_text(encoding='utf-8'))['cases'];missions={m['id']:m for sit in lib['situations'] for m in sit['missions']}
  self.assertGreaterEqual(len(cases),162)
  for case in cases:
   m=missions[case['mission_id']];step=next(s for s in m['steps'] if s['id']==case['step_id']);out=st.match_step(step,case['text_sv']);self.assertEqual(out['id'] if out else None,case['expected_intent'],case)
  cafe=next(s for s in missions['lib_cafe_m1']['steps'] if s['id']=='request')
  for text in ['En kaffe, tack.','Jag tar en kaffe.']:self.assertEqual(st.match_step(cafe,text)['id'],'request_answer')
  for text in ['Jag drömmer om kaffe','Jag tar ingen kaffe']:self.assertIsNone(st.match_step(cafe,text))
 def test_natural_reply_corpus_uses_production_matcher(self):
  root=Path(__file__).resolve().parent.parent/'content';raw=(root/'library.json').read_bytes();lib=json.loads(raw);cases=json.loads((root/'natural_reply_evaluation.json').read_text(encoding='utf-8'))['cases'];report=json.loads((root/'natural_reply_results.json').read_text(encoding='utf-8'))['after']
  self.assertEqual(report['sha256'],hashlib.sha256(raw).hexdigest(),'content report must match frozen library')
  missions={m['id']:m for sit in lib['situations'] for m in sit['missions']};spec=importlib.util.spec_from_file_location('content_validator',root/'validate_library.py');validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
  valid=valid_ok=unsafe=unsafe_ok=0
  for case in cases:
   step=next(s for s in missions[case['mission_id']]['steps'] if s['id']==case['step_id']);match=st.match_step(step,case['text_sv']);actual=match['id'] if match else None
   self.assertEqual(actual,validator.match(step,case['text_sv']),('production/content evaluator disagree',case))
   if case['expected_intent'] is None:
    unsafe+=1;unsafe_ok+=actual is None
   else:
    valid+=1;valid_ok+=actual==case['expected_intent']
  self.assertEqual((valid,valid_ok),(report['valid_replies']['total'],report['valid_replies']['accepted_correctly']));self.assertEqual((unsafe,unsafe_ok),(report['unsafe_or_offtopic']['total'],report['unsafe_or_offtopic']['rejected_correctly']))
  print(f'PRODUCTION_MATCHER authored regression: valid {valid_ok}/{valid}; unsafe/off-topic rejected {unsafe_ok}/{unsafe}; cases {len(cases)}',flush=True)
if __name__=='__main__':unittest.main()
