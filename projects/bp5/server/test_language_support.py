import hashlib,json,unittest
from pathlib import Path
from language_support import language_support

ROOT=Path(__file__).resolve().parent
class LanguageSupportTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  artifact=json.loads((ROOT/'swedish_support_vocabulary.json').read_text(encoding='utf8'));cls.words=frozenset(artifact['words']);cls.source_hash=artifact['source_sha256']
 def test_vocabulary_is_derived_from_current_authored_content(self):
  source=ROOT.parent/'content'/'library.json';self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),self.source_hash)
  from build_swedish_support import extract
  self.assertEqual(self.words,frozenset(extract(json.loads(source.read_text(encoding='utf8')))))
 def test_short_swedish_lexical_support_is_not_raw_detector_label(self):
  self.assertEqual(language_support('En bulle tack.','request','zh',.152,.099,self.words),(True,'lexical_support'))
 def test_obvious_foreign_replies_and_nonlexical_short_inputs_not_supported(self):
  for text,label,top,sv in [('A bun please.','en',.969,.001),('Ein Brötchen bitte.','de',.904,.016),('En kaffe, tak.','da',.398,.035),('En bolle, tak.','pl',.166,.081),('Un café, s’il vous plaît.','fr',.99,0.0)]:
   with self.subTest(text=text):self.assertFalse(language_support(text,'request',label,top,sv,self.words)[0])
 def test_shared_confirmation_is_context_limited(self):
  self.assertEqual(language_support('Ja tack.','confirm','en',.73,.003,self.words),(True,'shared_confirmation'))
  self.assertFalse(language_support('Ja tack.','request','en',.73,.003,self.words)[0]);self.assertFalse(language_support('Ja, thanks.','confirm','en',.96,.001,self.words)[0])
 def test_invalid_detector_values_fail_closed(self):
  for label,top,sv in [('sv',float('nan'),.1),('sv',.9,float('inf')),('sv',True,.5),('english',.9,.1)]:
   with self.subTest(label=label):
    with self.assertRaises(ValueError):language_support('Hej','request',label,top,sv,self.words)
if __name__=='__main__':unittest.main()
