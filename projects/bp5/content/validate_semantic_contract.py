"""Contract regressions and provenance checks; no model or private corpus access.

Witnesses check specific reviewed semantic failures. These assertions do not
establish general Swedish comprehension, human judgement or learning efficacy.
"""
import argparse,copy,hashlib,json,unittest
from pathlib import Path
from build_semantic_review import indexed,incoming,sha,write
from validate_library import match
from library_sources.example_adjudication import exclusion_reason

ROOT=Path(__file__).parent
LIBRARY=ROOT/'library.candidate-2026-11-01.9.json'
REPORT_DIR=ROOT/'semantic_review'/'final-2026-11-01.9'
PRESERVED={'2026-11-01.7':'e2317c4172296a8377775f09866db9d4fe6b8995759c48fda6c1cc6efcc9a609','2026-11-01.8':'99be582abcdb920fc3c0b0dd59d5d3ad7359ac509f4c407ee64ab1f257702eca'}

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def final_nodes(missions):return [(m,s) for m in missions.values() for s in m['steps'] if s['id'].startswith('confirm_')]
def intent(step,key):return next(i for i in step['intents'] if i['id']==key)
def node(missions,mid,sid):return next(s for s in missions['lib_'+mid]['steps'] if s['id']==sid)

class SemanticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.library=read(LIBRARY);cls.missions=indexed(cls.library)

    def test_all_108_refusals_scope_actual_offer(self):
        finals=final_nodes(self.missions);self.assertEqual(len(finals),108)
        for mission,step in finals:
            with self.subTest(mission=mission['id'],step=step['id']):
                negative=intent(step,'decline');contract=negative['semantic_contract']
                self.assertEqual(contract['offer_sv'],incoming(mission,step)[0]['reply_sv'])
                self.assertEqual(contract['question_sv'],step['prompt_sv'])
                self.assertEqual(contract['required_meaning_sv'],negative['meaning_sv'])
                self.assertEqual(contract['required_meaning_en'],negative['meaning_en'])
                self.assertEqual(match(step,'Nej.'),'decline')
                self.assertIn('No shared alternative or reason is inferred',contract['example_inventory_role'])
                self.assertEqual(len(contract['not_entailed']),4)

    def test_canonical_refusals_do_not_depend_on_first_example(self):
        from library_sources import language_revision,basic,medium,high
        saved=copy.deepcopy(language_revision.ANSWERS)
        try:
            for yes,no in language_revision.ANSWERS.values():no.reverse()
            rebuilt=indexed({'situations':basic.situations()+medium.situations()+high.situations()})
            for m,s in final_nodes(self.missions):
                other=node(rebuilt,m['id'][4:],s['id'])
                for key in ['meaning_sv','meaning_en','reply_sv','semantic_contract']:
                    self.assertEqual(intent(s,'decline')[key],intent(other,'decline')[key],(m['id'],s['id'],key))
        finally:
            language_revision.ANSWERS.clear();language_revision.ANSWERS.update(saved)

    def test_specific_alternatives_are_subtypes_not_mandatory_meanings(self):
        witnesses=[
          ('cafe_m2','confirm_sandwich',['Kontant, tack.','Ja, men jag har inget kort.'],['cash','kontant']),
          ('reception_m3','confirm_downstairs',['Jag vill hellre stå.','Jag vill sitta någon annanstans.'],['standing','stand','somewhere else','stå','annanstans']),
          ('reception_m3','confirm_upstairs',['Jag tar trappan.','Jag behöver inte hissen.'],['stairs','trappan']),
          ('library_m1','confirm_story',['Jag vill bara titta i den.','Jag vill inte låna den än.'],['browse','later','titta','senare']),
          ('transport_m1','confirm_go',['Jag hittar själv.','Jag behöver ingen karta.'],['myself','on my own','hittar själv']),
          ('customer_service_m1','confirm_refund',['Det räcker att du berättar.','Jag behöver inga skriftliga instruktioner.'],['oral','verbally','berättar'])
        ]
        for mid,sid,examples,not_required in witnesses:
            step=node(self.missions,mid,sid);negative=intent(step,'decline')
            for text in examples:self.assertEqual(match(step,text),'decline',(mid,sid,text))
            minimal=(negative['meaning_en']+' '+negative['meaning_sv']+' '+negative['reply_sv']).casefold()
            for extra in not_required:self.assertNotIn(extra,minimal,(mid,sid,extra))

    def test_assistance_and_unspecified_delay_are_not_forced_refusals(self):
        for mid,sid,text in [
          ('cafe_m1','confirm_takeaway','Jag behöver hjälp att hämta kaffet.'),
          ('transport_m3','confirm_direct','Jag behöver hjälp att hitta dit.'),
          ('customer_service_m3','confirm_written','Jag väntar med bekräftelsen.'),
          ('customer_service_m3','confirm_explain','Jag väntar med bekräftelsen.')
        ]:
            step=node(self.missions,mid,sid)
            self.assertIsNone(match(step,text))
            self.assertEqual(match(step,'Nej, '+text[0].lower()+text[1:]),'decline')
            self.assertIsNotNone(exclusion_reason('lib_'+mid,step,intent(step,'decline'),text))

    def test_name_verification_truth_refusal_and_uncertainty_are_distinct(self):
        for _,step in final_nodes(self.missions):
            if step['prompt_sv']!='Stämmer det att namnet är Kim?':continue
            negative=intent(step,'decline')
            self.assertEqual(negative['semantic_contract']['predicate_kind'],'explicit_denial_or_explicit_refusal_to_verify')
            for text,wanted in [('Ja, det stämmer.','confirm'),('Nej, det stämmer inte.','decline'),('Jag heter inte Kim.','decline'),('Jag vill inte.','decline'),('Jag vet inte om namnet stämmer.',None),('Gärna.',None),('Det passar tyvärr inte.',None)]:
                self.assertEqual(match(step,text),wanted,(step['id'],text))

    def test_question_and_hypothesis_acts_and_notice_facts(self):
        hypothesis=node(self.missions,'community_project_m3','detail_2')
        self.assertTrue(hypothesis['speech_act_policy']['questions_allowed_when_they_propose_a_relevant_hypothesis'])
        inquiry=node(self.missions,'course_planning_m3','choice')
        self.assertTrue(inquiry['speech_act_policy']['questions_allowed'])
        for mid,iid in [('next_steps_m1','choose_class'),('next_steps_m3','choose_digital')]:
            self.assertTrue(intent(node(self.missions,mid,'choice'),iid)['speech_act_policy']['questions_allowed'])
        for sid,iid in [('detail_2','detail_2_answer'),('choice','choose_message')]:
            contract=intent(node(self.missions,'shared_home_m2',sid),iid)['semantic_contract']
            self.assertEqual(contract['required_facts'],['Notice is given the day before the planned visit.'])
            self.assertIn('No written channel is required.',contract['channel_rule'])

    def test_old_snapshots_and_graph_are_preserved(self):
        for version,digest in PRESERVED.items():
            path=ROOT/'snapshots'/('library-'+version+'.json');self.assertEqual(sha(path),digest)
            previous=indexed(read(path));self.assertEqual(set(previous),set(self.missions))
            for mid,m in self.missions.items():
                old=previous[mid]
                self.assertEqual(m['completion_objectives'],old['completion_objectives'])
                self.assertEqual(m['goal'],old['goal'])
                graph=lambda mission:{(s['id'],s['objective'],i['id'],i['next_step']) for s in mission['steps'] for i in s['intents']}
                self.assertEqual(graph(m),graph(old))

    def test_quarantine_is_conservative_and_original_is_immutable(self):
        manifest=read(ROOT/'natural_reply_adjudication.v2.json')
        self.assertEqual(sha(ROOT/'natural_reply_evaluation.json'),manifest['source_sha256'])
        summary=manifest['summary']
        self.assertEqual((summary['retained_case_contexts'],summary['quarantined_case_contexts'],summary['scoped_regression_contexts']),(1314,440,108))
        self.assertEqual(summary['replacement_labels_assigned'],0)
        self.assertEqual(summary['scoped_regression_distinct_texts'],1)
        removed=manifest['removed_or_quarantined_cases']
        self.assertEqual(len({r['case_id'] for r in removed}),548)
        for row in removed:
            self.assertFalse(row['eligible_for_gold']);self.assertFalse(row['eligible_for_training'])
            self.assertNotIn('expected_intent',row)

def write_inventory_manifest(library,output):
    old_path=ROOT/'snapshots'/'library-2026-11-01.8.json'
    before=indexed(read(old_path));rows=[]
    for mid,m in indexed(library).items():
        for step in m['steps']:
            old_step=next(s for s in before[mid]['steps'] if s['id']==step['id'])
            for item in step['intents']:
                old=intent(old_step,item['id'])
                removed=[x for x in old.get('exact_replies_sv',[]) if x not in item.get('exact_replies_sv',[])]
                added=[x for x in item.get('exact_replies_sv',[]) if x not in old.get('exact_replies_sv',[])]
                examples_changed=old['examples_sv']!=item['examples_sv']
                if removed or added or examples_changed:
                    exclusions=[{'text_sv':text,'reason':exclusion_reason(mid,step,item,text),'decision':'exclude_from_auto_accept_inventory_pending_context_review','new_gold_label':None} for text in removed]
                    assert all(r['reason'] for r in exclusions)
                    rows.append({'key':mid+'/'+step['id']+'/'+item['id'],'removed_exact_replies':exclusions,'added_exact_replies':added,'old_examples_sv':old['examples_sv'],'new_examples_sv':item['examples_sv'],'canonical_examples_changed':examples_changed})
    write(output,{'schema_version':'1.0','from_version':'2026-11-01.8','from_sha256':sha(old_path),'to_version':library['content_version'],'to_sha256':sha(LIBRARY),'note':'Source inventory adjudication, not a new language benchmark. Excluding an ambiguous auto-accept example does not assign an UNKNOWN gold label. Historical files and learner records remain unchanged.','counts':{'changed_intents':len(rows),'removed_exact_reply_contexts':sum(len(r['removed_exact_replies']) for r in rows),'added_exact_reply_contexts':sum(len(r['added_exact_replies']) for r in rows),'canonical_examples_changed':sum(r['canonical_examples_changed'] for r in rows)},'changes':rows})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,default=LIBRARY);parser.add_argument('--report-dir',type=Path,default=REPORT_DIR)
    args=parser.parse_args();LIBRARY=args.library;REPORT_DIR=args.report_dir;REPORT_DIR.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SemanticContractTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_inventory_manifest(read(LIBRARY),REPORT_DIR/'example-inventory-adjudication.json')
    write(REPORT_DIR/'semantic-validation.json',{'content_version':read(LIBRARY)['content_version'],'source_sha256':sha(LIBRARY),'passed':result.wasSuccessful(),'test_methods':result.testsRun,'failures':[str(x[0]) for x in result.failures],'errors':[str(x[0]) for x in result.errors],'scope':['All 108 final predicates reference their actual authored offer.','Reordering illustrative refusal examples cannot change any final refusal predicate or response.','Specific alternative witnesses, assistance ambiguity, name verification and permitted question acts are checked.','Stable graphs and immutable .7/.8 snapshots are verified.','Synthetic adjudication conserves all original cases and assigns no replacement labels.'],'limitations':['These are engineering and authored semantic regressions, not independent language comprehension or learner-effectiveness results.','The lexical matcher remains deliberately narrow; exclusion from its inventory is not a semantic UNKNOWN gold label.']})
    raise SystemExit(0 if result.wasSuccessful() else 1)
