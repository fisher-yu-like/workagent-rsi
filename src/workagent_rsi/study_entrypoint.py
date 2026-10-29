"""Default-off public qualification and study preparation entrypoints."""
import argparse
import json
from pathlib import Path

from .hashing import canonical_json_hash, sha256_file
from .study_protocol import StudyConfig, prepare_experiment, freeze_manifest, read_tasks


def qualification_report(root):
    repairs={domain:[] for domain in ('excel','word','powerpoint')}
    for path in Path(root).rglob('attempt-manifest.json'):
        data=json.loads(path.read_text(encoding='utf-8'))
        attempts=data.get('attempts',[])
        # Only naturally observed failed initial executions with an actual
        # second attempt and successful reassessment establish repair evidence.
        if len(attempts)<2 or attempts[0].get('state')!='FAILED':continue
        request_path=path.parent/'attempt-001'/'request.json'
        code_path=path.parent/'attempt-000'/'code-manifest.json'
        if not request_path.is_file() or not code_path.is_file():continue
        request=json.loads(request_path.read_text(encoding='utf-8'))
        code=json.loads(code_path.read_text(encoding='utf-8'))
        if not code.get('sources') or request.get('task',{}).get('domain') not in repairs:continue
        failure=attempts[0].get('failure') or {}
        if failure and failure.get('failure_origin') not in {'agent_execution','artifact_defect'}:continue
        selected=attempts[data['selected_attempt']]
        if selected.get('state')!='SUCCEEDED' or not selected.get('artifacts'):continue
        for artifact in selected['artifacts']:
            artifact_path=Path(artifact.get('path',''))
            extension=artifact_path.suffix.lower()
            domain={'.xlsx':'excel','.docx':'word','.pptx':'powerpoint'}.get(extension)
            if (domain and domain==request['task']['domain'] and artifact_path.is_file()
                    and artifact.get('sha256')==sha256_file(artifact_path)):
                repairs[domain].append(str(path))
    return {'three_domain_repair_complete':all(repairs.values()),'natural_repair_evidence':repairs,
            'research_qualified':False,'human_judge_calibration':'pending',
            'scope':'structural_and_deterministic_qualification_only'}


def run_qualification(manifest, root, *, resume=False):
    if not manifest['live_ready']:
        raise ValueError('live qualification blocked: '+', '.join(manifest['blockers']))
    config=StudyConfig.model_validate(manifest['config'])
    # Recheck every frozen local input immediately before dispatch.
    if prepare_experiment(config)!=manifest:
        raise ValueError('study inputs changed after preparation')
    from .workagent_provider import WorkAgentConfig, WorkAgentSkill
    from .candidate_provider import OpenAIChatCandidateProvider
    from .workagent_experiment import WorkAgentExperimentRunner
    from .run_budget import RunBudget
    from .repair_loop import RepairPolicy
    batches,families=read_tasks(config.tasks_file)
    workagent=WorkAgentConfig.model_validate_json(Path(config.workagent_config_file).read_text(encoding='utf-8'))
    if (workagent.backend,workagent.model,workagent.api_base_url.rstrip('/')) != (
            config.provider,config.model,config.endpoint.rstrip('/')):
        raise ValueError('executor identity differs from approved study identity')
    if canonical_json_hash(workagent.sandbox_policy.model_dump(mode='json')) != config.sandbox_digest:
        raise ValueError('sandbox policy differs from qualified digest')
    skill=WorkAgentSkill.model_validate_json(Path(config.initial_skill_file).read_text(encoding='utf-8'))
    assessment=json.loads(Path(config.assessment_config_file).read_text(encoding='utf-8'))
    freeze_manifest(manifest,root,resume=resume)
    budget=RunBudget(max_model_calls=config.max_model_calls,max_tool_calls=config.max_tool_calls,
                     max_wall_seconds=float(config.max_wall_seconds),max_repairs=config.max_repairs)
    provider=OpenAIChatCandidateProvider(model=config.model,api_base_url=config.endpoint,
                                        api_key_env=config.api_key_env,max_retries=0)
    runner=WorkAgentExperimentRunner(workagent_config=workagent,input_base=config.input_base,
        assessment_config=assessment,run_budget=budget,
        repair_policy=RepairPolicy(max_repairs=config.max_repairs,total_deadline_seconds=config.max_wall_seconds))
    try:
        result=runner.run(batches,skill,provider,Path(root)/'outer-loop',rounds=1,
            family_manifest=families,resume=resume,
            comparison_policy={**config.comparison_policy,'required_repeats':config.repeats})
    finally:
        report=qualification_report(root)
        (Path(root)/'three-domain-repair-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return result


def main(kind, argv=None):
    parser=argparse.ArgumentParser(description='Prepare or run a frozen Office '+kind+' protocol')
    default=Path(__file__).resolve().parents[2]/'project_artifacts/phase3_experiments/configs'/(
        'live_qualification_v2.json' if kind=='qualification' else 'rsi_comparison_v2.json')
    parser.add_argument('--config',type=Path,default=default)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--resume',type=Path)
    parser.add_argument('--output',type=Path,help='Write the offline preparation report')
    args=parser.parse_args(argv)
    config=StudyConfig.model_validate_json(args.config.read_text(encoding='utf-8'))
    if config.kind!=kind:parser.error('configuration kind differs from entrypoint')
    manifest=prepare_experiment(config)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as handle:json.dump(manifest,handle,indent=2)
    if args.dry_run:
        print(json.dumps(manifest,indent=2));return 0
    if kind=='comparison':
        # Existing providers meter calls/tools/time, but lack a qualified total
        # token limiter. Do not silently substitute a call cap for a token cap.
        print(json.dumps({'status':'blocked','blockers':manifest['blockers']+
              ['metered_four_arm_dispatch_not_qualified'], 'paid_calls':0}));return 2
    if not manifest['live_ready']:
        print(json.dumps({'status':'blocked','blockers':manifest['blockers'],'paid_calls':0}));return 2
    result=run_qualification(manifest,args.resume or config.output_root,resume=args.resume is not None)
    print(json.dumps(result,indent=2));return 0 if result.get('status')=='completed' else 2
