import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import operation_guard as guard
import project_files as project


class ProjectBehavior(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        project.init(self.root, 'restaurant')

    def tearDown(self):
        self.tmp.cleanup()

    def load_state(self):
        return json.loads((self.root/'STATE.json').read_text())

    def state(self, value):
        (self.root/'STATE.json').write_text(json.dumps(value))

    def plan_tickets(self, tickets):
        data = {'schema_version':'0.1','spec_sha256':project.sha(self.root/'SPEC.md'),'tickets':tickets}
        (self.root/'TICKETS.md').write_text('# 任务\n\n```json\n'+json.dumps(data)+'\n```\n')

    def ready(self):
        self.plan_tickets([{'id':'S01','kind':'shot','source_mode':'generate','blocked_by':[],
                            'acceptance':['完整播放人物与动作稳定'],'duration_s':2,'max_attempts':2}])
        s = self.load_state()
        s['project_id'] = 'p01'
        s['revision_token'] = 'sha256-project-1'
        for key, file in [('spec','SPEC.md'),('tickets','TICKETS.md')]:
            s['approvals'][key]={'sha256':project.sha(self.root/file), 'approved_by':'user',
                                  'user_evidence':'case fixture explicit approval'}
        s['budget']={'approved_by':'user','user_evidence':'fixture approves up to 6 credits, 3 calls',
                     'unit':'credits','limit':6,'spent':0,'reserved':0,'max_generation_calls':3,
                     'generation_calls_used':0,'allowed_ticket_ids':['S01'],
                     'spec_sha256':project.sha(self.root/'SPEC.md'),
                     'tickets_sha256':project.sha(self.root/'TICKETS.md')}
        self.state(s)
        p={'operation_id':'op1','project_id':'p01','ticket_id':'S01','intent':'generate',
           'may_charge':True,'cost_upper_bound':2,'cost_unit':'credits','cost_evidence':'fixture verified 2 credit cap',
           'expected_revision':s['revision_token'],'idempotency_key':'key1',
           'request':{'projectId':'p01','run':True,'expectedRevision':s['revision_token'],'idempotencyKey':'key1'}}
        p['payload_sha256']=guard.canonical(p['request'])
        return s,p

    def errors(self,p):
        return guard.check(self.root/'STATE.json',p)

    def test_init_and_draft_check(self):
        self.assertEqual(project.inspect(self.root),[])
        self.assertTrue(project.inspect(self.root,ready=True))

    def test_init_never_overwrites(self):
        (self.root/'SPEC.md').write_text('customer content')
        with self.assertRaises(ValueError):project.init(self.root,'factory')
        self.assertEqual((self.root/'SPEC.md').read_text(),'customer content')

    def test_human_approved_ready(self):
        self.ready()
        self.assertEqual(project.inspect(self.root,True),[])

    def test_changed_spec_invalidates_approval_and_tickets(self):
        self.ready()
        with (self.root/'SPEC.md').open('a') as f:f.write(' changed scene')
        errors=project.inspect(self.root,True)
        self.assertTrue(any('spec_sha256 is stale' in x for x in errors))
        self.assertTrue(any('human approval: spec' in x for x in errors))

    def test_selected_is_not_approved(self):
        s,p=self.ready()
        s['approvals']['spec']['approved_by']=None
        self.state(s)
        self.assertTrue(any('human approval' in x for x in self.errors(p)))

    def test_dependency_cycle(self):
        tickets=[{'id':a,'kind':'shot','source_mode':'reuse','blocked_by':[b],'acceptance':['play']} for a,b in [('A','B'),('B','A')]]
        self.plan_tickets(tickets)
        self.assertTrue(any('cycle' in x for x in project.inspect(self.root)))

    def test_missing_dependency(self):
        self.plan_tickets([{'id':'A','kind':'edit','source_mode':'deterministic','blocked_by':['not-there'],'acceptance':['play']}])
        self.assertTrue(any('missing blocker' in x for x in project.inspect(self.root)))

    def test_changed_approved_asset(self):
        s,p=self.ready()
        (self.root/'product.png').write_bytes(b'original')
        s['assets']=[{'id':'prod01','local_path':'product.png','sha256':project.sha(self.root/'product.png'),'status':'approved'}]
        self.state(s)
        (self.root/'product.png').write_bytes(b'different')
        self.assertTrue(any('changed local asset' in x for x in self.errors(p)))

    def test_valid_paid_preflight_is_read_only(self):
        s,p=self.ready()
        before=(self.root/'STATE.json').read_bytes()
        self.assertEqual(self.errors(p),[])
        self.assertEqual((self.root/'STATE.json').read_bytes(),before)

    def test_unknown_price_denied(self):
        s,p=self.ready()
        p['cost_upper_bound']=None
        p['cost_evidence']=None
        self.assertTrue(any('cost_upper_bound' in x for x in self.errors(p)))
        self.assertTrue(any('quote/free evidence' in x for x in self.errors(p)))

    def test_free_generation_still_needs_explicit_approval(self):
        s,p=self.ready()
        p['cost_upper_bound']=0
        s['budget']['approved_by']=None
        self.state(s)
        self.assertTrue(any('budget approval' in x for x in self.errors(p)))

    def test_budget_includes_reserved_and_spent(self):
        s,p=self.ready()
        s['budget'].update(spent=3,reserved=2)
        self.state(s)
        self.assertTrue(any('upper bound exceeded' in x for x in self.errors(p)))

    def test_unknown_submission_blocks_new_spend(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':'op0','idempotency_key':'key0','status':'unknown','may_charge':True}]
        self.state(s)
        self.assertTrue(any('unsettled charging' in x for x in self.errors(p)))

    def test_duplicate_key_requires_reconciliation(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':'other','idempotency_key':'key1','status':'succeeded','may_charge':True}]
        self.state(s)
        self.assertTrue(any('already exists' in x for x in self.errors(p)))

    def test_stale_revision_rejected(self):
        s,p=self.ready()
        p['expected_revision']='graphRevision-not-project'
        self.assertTrue(any('revision_token' in x for x in self.errors(p)))

    def test_request_project_mismatch_rejected(self):
        s,p=self.ready()
        p['request']['projectId']='other-customer'
        p['payload_sha256']=guard.canonical(p['request'])
        self.assertTrue(any('projectId differs' in x for x in self.errors(p)))

    def test_run_true_cannot_hide_in_noncharging_plan(self):
        s,p=self.ready()
        p['may_charge']=False
        p['cost_upper_bound']=0
        self.assertTrue(any('run=true' in x for x in self.errors(p)))

    def test_bool_and_nan_not_valid_costs(self):
        s,p=self.ready()
        for value in (True,float('nan'),float('inf'),-1):
            p['cost_upper_bound']=value
            self.assertTrue(any('cost_upper_bound' in x for x in self.errors(p)),repr(value))

    def test_payload_hash_detects_changed_prompt(self):
        s,p=self.ready()
        p['request']['prompt']='new prompt'
        self.assertTrue(any('hash mismatch' in x for x in self.errors(p)))

    def test_attempt_cap(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':str(i),'idempotency_key':str(i),'status':'failed','intent':'generate','ticket_id':'S01','may_charge':True} for i in range(2)]
        self.state(s)
        self.assertTrue(any('attempt ceiling' in x for x in self.errors(p)))

    def test_call_cap(self):
        s,p=self.ready()
        s['budget']['generation_calls_used']=3
        self.state(s)
        self.assertTrue(any('call ceiling' in x for x in self.errors(p)))

    def test_cli_rejects_bad_json_cleanly(self):
        path=self.root/'plan.json'
        path.write_text('{broken')
        r=subprocess.run([sys.executable,str(SCRIPT_DIR/'operation_guard.py'),str(self.root/'STATE.json'),str(path)],capture_output=True,text=True)
        self.assertEqual(r.returncode,1)
        self.assertFalse(json.loads(r.stdout)['ok'])

    def test_unknown_operation_missing_charge_flag_denied(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':'old','idempotency_key':'old-key','status':'unknown'}]
        self.state(s)
        self.assertTrue(any('may_charge' in x for x in self.errors(p)))

    def test_stale_generation_counter_denied(self):
        s,p=self.ready()
        s['budget']['max_generation_calls']=1
        s['operations']=[{'operation_id':'old','idempotency_key':'old-key','status':'succeeded',
                          'intent':'generate','ticket_id':'S01','counts_as_attempt':True,'may_charge':True,
                          'cost_upper_bound':2,'cost_unit':'credits','actual_cost':2,'settlement_evidence':'receipt'}]
        self.state(s)
        self.assertTrue(any('generation_calls_used lags' in x for x in self.errors(p)))

    def test_cancelled_effective_attempts_count(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':str(i),'idempotency_key':str(i),'status':'cancelled',
                          'intent':'generate','ticket_id':'S01','counts_as_attempt':True,'may_charge':True,
                          'cost_upper_bound':0,'cost_unit':'credits'} for i in range(2)]
        s['budget']['generation_calls_used']=2
        self.state(s)
        self.assertTrue(any('attempt ceiling' in x for x in self.errors(p)))

    def test_spend_aggregate_cannot_ignore_prior_operation(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':'old','idempotency_key':'old-key','status':'failed',
                          'intent':'generate','ticket_id':'S01','counts_as_attempt':True,'may_charge':True,
                          'cost_upper_bound':5,'cost_unit':'credits'}]
        s['budget']['generation_calls_used']=1
        self.state(s)
        self.assertTrue(any('budget aggregate lags' in x for x in self.errors(p)))

    def test_approved_remote_asset_needs_stable_reference(self):
        s,p=self.ready()
        s['assets']=[{'id':'prod01','status':'approved','ref':'https://example.invalid/expired'}]
        self.state(s)
        self.assertTrue(any('stable media_id' in x for x in self.errors(p)))

    def test_changed_asset_binding_denied_even_when_new_hash_matches_file(self):
        s,p=self.ready()
        (self.root/'product.png').write_bytes(b'old')
        asset={'id':'prod01','local_path':'product.png','sha256':project.sha(self.root/'product.png'),
               'status':'approved','media_id':None,'ref':None}
        s['assets']=[asset]
        data={'schema_version':'0.1','spec_sha256':project.sha(self.root/'SPEC.md'),
              'tickets':[{'id':'S01','kind':'shot','source_mode':'generate','blocked_by':[],
                          'asset_ids':['prod01'],'acceptance':['play'],'max_attempts':2}]}
        (self.root/'TICKETS.md').write_text('# tickets\n\n```json\n'+json.dumps(data)+'\n```\n')
        ticket_hash=project.sha(self.root/'TICKETS.md')
        s['approvals']['tickets']['sha256']=ticket_hash
        s['budget']['tickets_sha256']=ticket_hash
        s['approvals']['spec']['asset_bindings']={'prod01':{k:asset.get(k) for k in ('sha256','media_id','ref')}}
        self.state(s)
        self.assertEqual(self.errors(p),[])
        (self.root/'product.png').write_bytes(b'new')
        s['assets'][0]['sha256']=project.sha(self.root/'product.png')
        self.state(s)
        self.assertTrue(any('human-approved binding' in x for x in self.errors(p)))

    def test_init_uses_utf8_with_ascii_locale(self):
        target=self.root/'ascii-environment'
        env=dict(os.environ,LC_ALL='C',PYTHONUTF8='0',PYTHONCOERCECLOCALE='0')
        r=subprocess.run([sys.executable,str(SCRIPT_DIR/'project_files.py'),'init',str(target)],env=env,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue((target/'SPEC.md').read_text(encoding='utf-8').startswith('# 视频'))

    def test_pre_submission_cancellation_does_not_consume_call(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':'not-sent','idempotency_key':'not-sent-key','status':'cancelled',
                          'intent':'generate','ticket_id':'S01','counts_as_attempt':False,'may_charge':True,
                          'cost_upper_bound':2,'cost_unit':'credits','submission_status':'not_sent',
                          'actual_cost':0,'settlement_evidence':'local cancellation before any tool dispatch'}]
        self.state(s)
        self.assertEqual(self.errors(p),[])

    def test_cancelled_without_no_submission_evidence_still_counts(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':'old','idempotency_key':'old-key','status':'cancelled',
                          'intent':'generate','ticket_id':'S01','counts_as_attempt':False,'may_charge':True,
                          'cost_upper_bound':0,'cost_unit':'credits','actual_cost':0,'settlement_evidence':'zero charge'}]
        self.state(s)
        self.assertTrue(any('generation_calls_used lags' in x for x in self.errors(p)))

    def test_failed_generations_cannot_clear_attempt_flag_without_evidence(self):
        s,p=self.ready()
        s['operations']=[{'operation_id':str(i),'idempotency_key':str(i),'status':'failed',
                          'intent':'generate','ticket_id':'S01','counts_as_attempt':False,'may_charge':True,
                          'cost_upper_bound':0,'cost_unit':'credits','actual_cost':0,'settlement_evidence':'zero charge'} for i in range(2)]
        s['budget']['generation_calls_used']=2
        self.state(s)
        self.assertTrue(any('non_execution_evidence' in x for x in self.errors(p)))

    def test_future_selected_asset_does_not_block_current_frontier_ticket(self):
        s,p=self.ready()
        data={'schema_version':'0.1','spec_sha256':project.sha(self.root/'SPEC.md'),'tickets':[
            {'id':'S01','kind':'shot','source_mode':'generate','blocked_by':[],'acceptance':['play']},
            {'id':'S02','kind':'shot','source_mode':'generate','blocked_by':['S01'],
             'asset_ids':['future'],'acceptance':['play']}]}
        (self.root/'TICKETS.md').write_text('# tickets\n\n```json\n'+json.dumps(data)+'\n```\n')
        ticket_hash=project.sha(self.root/'TICKETS.md')
        s['approvals']['tickets']['sha256']=ticket_hash
        s['budget']['tickets_sha256']=ticket_hash
        s['assets']=[{'id':'future','status':'selected','ref':'pending-generation'}]
        self.state(s)
        self.assertEqual(self.errors(p),[])
        self.assertTrue(any('unapproved required asset' in x for x in project.inspect(self.root,True)))

    def test_malformed_asset_record_returns_errors_without_crash(self):
        s,p=self.ready()
        s['assets']=[None]
        self.state(s)
        self.assertTrue(any('invalid asset record' in x for x in self.errors(p)))

    def test_explicit_local_dialogue_revision_reuses_existing_budget(self):
        s,p=self.ready()
        (self.root/'SPEC.md').write_text('# SPEC\n第二句：今天来看看；人物、产品和时长不变。\n',encoding='utf-8')
        tickets=[{'id':'S01','kind':'audio','source_mode':'generate','blocked_by':[],
                  'audio':'今天来看看','acceptance':['只改第二句，其余保持']},
                 {'id':'S02','kind':'shot','source_mode':'reuse','blocked_by':[],
                  'acceptance':['沿用原片']}]
        self.plan_tickets(tickets)
        s['assets']=[{'id':'product','status':'approved','media_id':'stable-product','ref':'provider:stable-product'}]
        original_binding={'product':{'sha256':None,'media_id':'stable-product','ref':'provider:stable-product'}}
        s['approvals']['spec']['asset_bindings']=copy.deepcopy(original_binding)
        for key,file in [('spec','SPEC.md'),('tickets','TICKETS.md')]:
            s['approvals'][key]['sha256']=project.sha(self.root/file)
            s['budget'][key+'_sha256']=project.sha(self.root/file)
        s['budget'].update(spent=1,reserved=1,generation_calls_used=1)
        s['operations']=[{'operation_id':'old','idempotency_key':'old-key','status':'succeeded',
                          'intent':'generate','ticket_id':'S01','counts_as_attempt':True,'may_charge':True,
                          'cost_upper_bound':1,'cost_unit':'credits','actual_cost':1,'settlement_evidence':'old receipt'}]
        self.state(s)
        self.assertEqual(self.errors(p),[])
        old_budget=copy.deepcopy(s['budget'])
        old_approvals=copy.deepcopy(s['approvals'])
        (self.root/'SPEC.md').write_text((self.root/'SPEC.md').read_text().replace('今天来看看','周末来看看'),encoding='utf-8')
        tickets[0]['audio']='周末来看看'
        self.plan_tickets(tickets)
        self.assertTrue(any('stale' in x for x in self.errors(p)))
        # Agent applies the explicitly authorized delta; this is not a new budget approval.
        evidence={'user_evidence':'第二句改成周末来看看，其他不变','affected_ticket_ids':['S01'],
                  'before':{k:v['sha256'] for k,v in old_approvals.items()},
                  'after':{'spec':project.sha(self.root/'SPEC.md'),'tickets':project.sha(self.root/'TICKETS.md')}}
        for key in ('spec','tickets'):
            s['approvals'][key]['sha256']=evidence['after'][key]
            s['approvals'][key]['revision_evidence']=copy.deepcopy(evidence)
            s['budget'][key+'_sha256']=evidence['after'][key]
        s['budget']['revision_evidence']=copy.deepcopy(evidence)
        self.state(s)
        self.assertEqual(self.errors(p),[])
        for field in ('approved_by','user_evidence','limit','spent','reserved','max_generation_calls',
                      'generation_calls_used','allowed_ticket_ids'):
            self.assertEqual(s['budget'][field],old_budget[field])
        self.assertEqual(s['approvals']['spec']['asset_bindings'],original_binding)
        self.assertEqual(s['operations'][0]['operation_id'],'old')

    def test_explicit_dialogue_request_does_not_authorize_new_spend_scope(self):
        s,p=self.ready()
        s['budget']['allowed_ticket_ids']=[]
        s['budget']['revision_evidence']={'user_evidence':'只改第二句，其他不变'}
        self.state(s)
        self.assertTrue(any('outside approved spend scope' in x for x in self.errors(p)))

    def test_explicit_dialogue_request_does_not_create_budget_approval(self):
        s,p=self.ready()
        s['budget']['approved_by']=None
        s['budget']['revision_evidence']={'user_evidence':'只改第二句，其他不变'}
        self.state(s)
        self.assertTrue(any('human budget approval' in x for x in self.errors(p)))


if __name__=='__main__':unittest.main(verbosity=2)
