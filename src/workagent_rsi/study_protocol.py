"""Offline preparation and immutable accounting for T31/T32 studies."""
import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import TaskSpec
from .dataset_splits import TaskFamilyManifest, validate_family_splits
from .hashing import canonical_json_hash, sha256_file
from .run_contracts import LiveCallPolicy
from .statistical_promotion import ComparisonPolicy


class StudyConfig(BaseModel):
    model_config=ConfigDict(extra='forbid', allow_inf_nan=False)
    schema_version: Literal['office-study-v2']='office-study-v2'
    kind: Literal['qualification','comparison']='qualification'
    allow_live_calls: bool=False
    provider: Literal['openai-chat']='openai-chat'
    model: str=Field(min_length=1)
    endpoint: str=Field(min_length=1)
    api_key_env: str='OPENAI_API_KEY'
    tasks_file: str | None=None
    input_base: str='.'
    initial_skill_file: str | None=None
    workagent_config_file: str | None=None
    assessment_config_file: str | None=None
    capability_receipt: str | None=None
    capability_sha256: str | None=None
    sandbox_digest: str | None=None
    live_policy_file: str | None=None
    output_root: str='project_artifacts/results/study-v2'
    rounds: int=Field(default=1,ge=1,le=6)
    repeats: int=Field(default=3,ge=3)
    max_model_calls: int=Field(default=24,ge=1)
    max_tool_calls: int=Field(default=64,ge=1)
    max_wall_seconds: int=Field(default=1200,ge=1)
    max_tokens: int | None=Field(default=None,ge=1)
    max_repairs: int=Field(default=1,ge=0,le=4)
    expanded_six_rounds_approved: bool=False
    final_store: str | None=None
    final_hash: str | None=None
    comparison_policy: dict=Field(default_factory=dict)


def read_tasks(path):
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    splits={s:[TaskSpec.model_validate(t) for t in rows] for s,rows in payload['splits'].items()}
    if set(splits)!={'develop','regression','hidden','ood_transfer'}:
        raise ValueError('study requires exactly four adaptive splits; final stays separate')
    ids=[t.task_id for rows in splits.values() for t in rows]
    if len(ids)!=len(set(ids)):
        raise ValueError('task IDs overlap between study splits')
    if any({t.domain for t in rows}!={'excel','word','powerpoint'} for rows in splits.values()):
        raise ValueError('every adaptive split must cover all three Office domains')
    families=[TaskFamilyManifest.model_validate(row) for row in payload['family_manifest']]
    validate_family_splits(families)
    if any(r.split=='final_test' for r in families):
        raise ValueError('final families cannot enter adaptive input')
    for split,rows in splits.items():
        role='promotion_validation' if split=='hidden' else split
        expected={v:r.domain for r in families if r.split==role for v in r.variant_ids}
        if expected!={t.task_id:t.domain for t in rows}:
            raise ValueError('task family binding differs from adaptive split')
    return splits,families


def prepare_experiment(config: StudyConfig | dict) -> dict:
    """No environment probes, credential reads, network or process execution."""
    config=StudyConfig.model_validate(config)
    LiveCallPolicy.credential_free_endpoint(config.endpoint)
    ComparisonPolicy(**{**config.comparison_policy,'required_repeats':config.repeats})
    if config.kind=='qualification' and config.rounds!=1:
        raise ValueError('qualification validates one outer round')
    if config.kind=='comparison' and config.rounds not in {3,6}:
        raise ValueError('comparison starts with a three-round pilot')
    if config.rounds==6 and not config.expanded_six_rounds_approved:
        raise ValueError('six rounds require a separately approved expansion')
    blockers=[]
    frozen={}
    for field in ('tasks_file','initial_skill_file','workagent_config_file','assessment_config_file',
                  'capability_receipt','live_policy_file'):
        value=getattr(config,field)
        if not value or not Path(value).is_file():
            blockers.append('missing_'+field)
        else:
            frozen[field]={'path':str(Path(value).resolve()),'sha256':sha256_file(Path(value))}
    count=0
    if 'tasks_file' in frozen:
        batches,families=read_tasks(config.tasks_file)
        count=sum(len(rows) for rows in batches.values())
        split_hashes={s:canonical_json_hash([t.model_dump(mode='json') for t in rows]) for s,rows in batches.items()}
    else:
        split_hashes={}
    if 'capability_receipt' in frozen:
        receipt=json.loads(Path(config.capability_receipt).read_text(encoding='utf-8'))
        if frozen['capability_receipt']['sha256']!=config.capability_sha256:
            blockers.append('capability_receipt_hash_mismatch')
        if not (receipt.get('qualified') is True and receipt.get('sandbox_digest')==config.sandbox_digest
                and receipt.get('provider')==config.provider and receipt.get('model')==config.model
                and receipt.get('endpoint')==config.endpoint and receipt.get('evidence_refs')):
            blockers.append('unqualified_model_or_sandbox_capability')
        if config.kind=='comparison' and receipt.get('hard_token_budget') is not True:
            blockers.append('hard_token_budget_not_qualified')
    if not config.sandbox_digest:
        blockers.append('missing_sandbox_digest')
    if not config.allow_live_calls:
        blockers.append('live_calls_disabled')
    if 'live_policy_file' in frozen:
        policy=LiveCallPolicy.model_validate_json(Path(config.live_policy_file).read_text(encoding='utf-8'))
        try:
            policy.require_authorized(provider=config.provider,model=config.model,endpoint=config.endpoint)
        except ValueError as exc:
            blockers.append(str(exc))
        factor=4 if config.kind=='comparison' else 1
        if any(getattr(policy,k) is None or factor*getattr(config,k)>getattr(policy,k)
               for k in ('max_model_calls','max_tool_calls','max_wall_seconds')):
            blockers.append('requested_caps_exceed_approval')
        if policy.max_cost_usd is not None:
            blockers.append('cost_upper_bound_not_qualified_for_this_entrypoint')
    if config.kind=='comparison':
        if config.max_tokens is None: blockers.append('missing_equal_token_cap')
        if not config.final_store or not config.final_hash: blockers.append('missing_sealed_final_evaluator')
    caps={k:getattr(config,k) for k in ('max_model_calls','max_tool_calls','max_wall_seconds','max_tokens')}
    # Feedback baseline + paired arms, plus the optimizer and bounded task-local
    # repair attempts; every model/tool retry consumes these same run caps.
    execution_attempts=count*config.repeats*3*config.rounds
    manifest={'schema_version':'frozen-office-experiment-v2','kind':config.kind,
        'config':config.model_dump(mode='json'),'inputs':frozen,'split_hashes':split_hashes,
        'task_count':count,'execution_attempt_upper_bound':execution_attempts*(1+config.max_repairs),
        'model_call_hard_cap':config.max_model_calls,'tool_call_hard_cap':config.max_tool_calls,
        'all_arm_model_call_cap':config.max_model_calls*(4 if config.kind=='comparison' else 1),
        'budget_may_exhaust_before_completion':True,'dry_run_paid_calls':0,
        'execution_seed':'not_supported','bootstrap_seed':config.comparison_policy.get('bootstrap_seed',20261016),
        'edit_budget_schedule':[3,3,2,2,1,1][:config.rounds], 'editable_fields':['instructions'],
        'arms':{'B0':{'policy':'fixed_single','caps':caps,'equal_cost_claim':False},
                'B1':{'policy':'fixed_task_repair','caps':caps},
                'B2':{'policy':'one_skill_update','caps':caps},
                'B3':{'policy':'multi_round_rsi','caps':caps}} if config.kind=='comparison' else {},
        'fixed_reference':['initial_champion','final_champion'],
        'final_protocol':'one sealed evaluator invocation after all arm selection; failure consumes invocation',
        'research_qualified':False, 'live_ready':not blockers,'blockers':sorted(set(blockers))}
    manifest['manifest_hash']=canonical_json_hash(manifest)
    return manifest


def freeze_manifest(manifest, root, *, resume=False):
    root=Path(root);path=root/'pre-registered-manifest.json'
    if resume:
        previous=json.loads(path.read_text(encoding='utf-8'))
        if previous!=manifest:
            raise ValueError('frozen experiment identity changed; create a new cohort')
    else:
        root.mkdir(parents=True,exist_ok=True)
        if any(root.iterdir()):raise FileExistsError('experiment root must be empty')
        path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return path


class StudyRecorder:
    """Append-only arm receipts; all four arms and fixed-reference pairs required."""
    def __init__(self, root, manifest):
        self.root=Path(root);self.manifest=manifest
        freeze_manifest(manifest,root,resume=(self.root/'pre-registered-manifest.json').exists())

    def record_arm(self, arm, receipt):
        if arm not in self.manifest['arms']:raise ValueError('unregistered study arm')
        if receipt.get('manifest_hash')!=self.manifest['manifest_hash']:
            raise ValueError('arm receipt belongs to another cohort')
        usage=receipt['usage'];caps=self.manifest['arms'][arm]['caps']
        for channel in ('model_calls','tool_calls','wall_seconds','tokens'):
            value=usage.get(channel);cap=caps.get('max_'+channel)
            if type(value) not in {int,float} or not math.isfinite(value) or value<0 or cap is None or value>cap:
                raise ValueError('unavailable or exceeded arm budget: '+channel)
        if not receipt.get('includes_optimizer_and_failed_calls'):
            raise ValueError('arm usage omits optimizer or failed calls')
        if set(receipt.get('fixed_reference',{}))!={'initial_champion','final_champion'}:
            raise ValueError('both champions must be reassessed on the frozen reference')
        path=self.root/f'{arm}.json'
        with path.open('x',encoding='utf-8') as handle:json.dump(receipt,handle,indent=2)

    def summarize(self):
        missing=[a for a in self.manifest['arms'] if not (self.root/f'{a}.json').is_file()]
        if missing:return {'status':'incomplete','missing_arms':missing,'research_qualified':False}
        arms={a:json.loads((self.root/f'{a}.json').read_text(encoding='utf-8')) for a in self.manifest['arms']}
        signal=arms['B3'].get('paired_comparison',{})
        return {'status':'complete_receipts','arms':arms,'research_qualified':False,
                'conclusion':'eligible_signal_requires_independent_validation' if signal.get('decision')=='eligible_statistical_signal'
                else 'no_demonstrated_gain', 'b0_equal_cost_claim':False}

    def evaluate_final_once(self, store, expected_hash, evaluate):
        if self.summarize()['status']!='complete_receipts':
            raise ValueError('all arms must finish selection before final evaluation')
        if (self.manifest['config']['final_hash']!=expected_hash or
                str(Path(self.manifest['config']['final_store']).resolve())!=str(store.root.resolve())):
            raise ValueError('final evaluator identity differs from preregistration')
        # One invocation assesses the frozen selection of all arms. The store
        # creates its one-use marker before dispatch and retains failed attempts.
        return store.evaluate_once(expected_hash,evaluate)


def execute_comparison(manifest, backend, root, *, resume=False):
    """Dispatch a frozen four-arm study through a trusted metered backend.

    The backend owns request-level token reservations and execution isolation;
    no current production backend satisfies that interface. An explicitly
    injected fixture may exercise this controller, never establish a live claim.
    A failed arm remains incomplete and cannot be omitted from the summary.
    """
    if manifest['kind']!='comparison':raise ValueError('not a comparison manifest')
    fixture=getattr(backend,'qualification_only',False)
    if not fixture and (not manifest['live_ready'] or not backend.hard_token_budget):
        raise ValueError('comparison requires qualified request-level token accounting')
    freeze_manifest(manifest,root,resume=resume)
    recorder=StudyRecorder(root,manifest)
    for arm,policy in manifest['arms'].items():
        completed=Path(root)/f'{arm}.json'
        if completed.exists():continue
        attempt=Path(root)/arm
        attempt.mkdir(exist_ok=resume)
        # A backend must restore its durable reservations, including interrupted
        # requests. This controller never resets or lends unused caps across arms.
        session=backend.begin_arm(arm,policy['caps'],attempt,resume=resume)
        if arm in {'B0','B1'}:
            selected=session.run_fixed(repairs=0 if arm=='B0' else manifest['config']['max_repairs'])
        else:
            rounds=1 if arm=='B2' else manifest['config']['rounds']
            selected=session.run_rsi(rounds=rounds,edit_budgets=manifest['edit_budget_schedule'][:rounds])
        references=session.reassess_fixed_reference(selected)
        receipt=session.finish(selected)
        receipt.update(manifest_hash=manifest['manifest_hash'],fixed_reference=references,
                       qualification_only=fixture)
        recorder.record_arm(arm,receipt)
    return recorder.summarize()
