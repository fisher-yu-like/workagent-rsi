"""Developer-visible feedback and explicit v1 comparison of artifact metrics."""

import json
import math
from pathlib import Path

from .assessment_contracts import RSIFeedback
from .artifact_feedback import public_issue_advice
from .hashing import canonical_json_hash


def candidate_diagnoses(diagnoses, *, split='develop', hidden_test=False):
    """Project typed develop hypotheses; private evidence never enters context."""
    from .rsi_contracts import FailureDiagnosis
    if split!='develop' or hidden_test:return []
    result=[]
    for item in diagnoses:
        diagnosis=FailureDiagnosis.model_validate(item.model_dump() if hasattr(item,'model_dump') else item)
        if diagnosis.feedback_visibility!='develop':continue
        if any(d.ref not in diagnosis.evidence_refs for d in diagnosis.evidence_details):
            raise ValueError('diagnosis details must cite an authorized diagnosis reference')
        result.append(diagnosis)
    return result


def candidate_feedback(feedback: RSIFeedback) -> RSIFeedback:
    """Allowlisted projection of developer data; unknown side channels are dropped.

    Split/visibility provenance is authoritative. Text inside approved develop
    observations remains untrusted data, never executable instructions.
    """
    feedback = RSIFeedback.model_validate(feedback.model_dump())
    task_fields = {'task_id', 'acceptance_status', 'quality_score', 'dimension_scores', 'coverage',
                   'errors', 'requirement_refs', 'trace_summary','task_acceptance','score_semantics',
                   'execution_status','execution_success','task_success','execution_error','diagnoses'}
    issue_fields = {'issue_id', 'requirement_id', 'kind', 'location', 'observed', 'expected', 'evidence_refs',
                    'severity', 'cause_hypothesis', 'repair_hint', 'skill_improvement_hint', 'recheck_ids', 'feedback_visibility',
                    'requested_location','observed_locations','failure_origin','affected_requirements','repair_action',
                    'verification_steps','impact','qualification_only'}
    protected = {'hidden', 'regression', 'ood', 'ood_transfer', 'final_test', 'promotion_validation',
                 'path', 'file_path', 'evidence_path', 'private_history', 'credentials'}
    def public(value):
        if isinstance(value, dict):
            if (value.get('hidden_test') or value.get('split', 'develop') != 'develop'
                    or value.get('feedback_visibility', 'develop') != 'develop'):
                return None
            return {k: public(v) for k,v in value.items() if k not in protected}
        if isinstance(value, list):
            return [item for v in value if (item := public(v)) is not None]
        return value
    tasks, groups = [], {}
    for row in feedback.tasks:
        if row.get('hidden_test') or row.get('split', 'develop') != 'develop':
            continue
        entry = {k: public(v) for k,v in row.items() if k in task_fields}
        if 'diagnoses' in entry:
            entry['diagnoses']=[d.model_dump(mode='json') for d in candidate_diagnoses(entry['diagnoses'])]
        if 'issues' in row:
            issues = []
            for issue in row['issues']:
                if (issue.get('hidden_test') or issue.get('split', 'develop') != 'develop'
                        or issue.get('feedback_visibility', 'develop') != 'develop'
                        or issue.get('kind', 'artifact_defect') != 'artifact_defect'):
                    continue
                clean = public({k: v for k,v in issue.items() if k in issue_fields})
                if clean is not None:
                    clean=public_issue_advice(clean)
                    issues.append(clean)
                    if clean.get('issue_id') and clean.get('requirement_id'):
                        # Original issue_groups can carry unapproved metadata.
                        key = clean['requirement_id']
                        groups.setdefault(key, []).append(f"{row['task_id']}:{clean['issue_id']}")
            entry['issues'] = issues
        tasks.append(entry)
    return RSIFeedback(mode=feedback.mode, tasks=tasks, issue_groups=groups)


def build_feedback(develop, *, mode="structured",execution_failures=None) -> RSIFeedback:
    if develop.get("split") != "develop":
        raise ValueError("only develop feedback can enter candidate context")
    tasks, groups = [], {}
    seen=set()
    for row in [*develop.get("rows", []),*(execution_failures if execution_failures is not None else develop.get('execution_failures',[]))]:
        if row.get("hidden_test"):
            continue
        if row['task_id'] in seen:continue
        seen.add(row['task_id'])
        if row.get('execution_failure'):
            outcome=row.get('execution_outcome') or {}
            if outcome.get('failure_origin')!='agent_execution' or outcome.get('status') not in {'failed','timeout'}:continue
            entry={'task_id':row['task_id'],'acceptance_status':'EXECUTION_FAILED','task_acceptance':'FAIL',
                'quality_score':None,'dimension_scores':{},'coverage':{},'execution_status':outcome['status'],
                'execution_success':False,'task_success':False,'score_semantics':'task-assessment-v2'}
            if mode!='score_only':entry['errors']=['Agent execution failed before a valid artifact was assessed.']
            if mode=='structured':
                error=row.get('execution_error') or {}
                entry['execution_error']={k:error[k] for k in ('message','failure_origin','content_boundary') if k in error}
                entry['diagnoses']=[d.model_dump(mode='json') for d in candidate_diagnoses(row.get('diagnoses',[]))]
            tasks.append(entry)
            continue
        score = row["score_report"]
        if score is None:continue
        entry = {"task_id": row["task_id"], "acceptance_status": score["acceptance_status"], "quality_score": score["total_score"], "dimension_scores": score["dimension_scores"], "coverage": score["coverage"]}
        entry.update(task_acceptance=score.get('task_acceptance','NOT_ASSESSED'),
            score_semantics=score.get('score_semantics','declared-check-v1'))
        issues = [i for i in row["issue_report"]["issues"] if i["feedback_visibility"] == "develop" and i["kind"] == "artifact_defect"]
        if mode == "brief":
            entry["errors"] = [i["requirement_id"] + ": requirement unmet" for i in issues]
        elif mode == "structured":
            entry["issues"] = issues
            for issue in issues:
                key = issue["requirement_id"]
                groups.setdefault(key, []).append(f"{row['task_id']}:{issue['issue_id']}")
        tasks.append(entry)
    return candidate_feedback(RSIFeedback(mode=mode, tasks=tasks, issue_groups=groups))


def feedback_with_requirements(feedback, develop_tasks):
    """Attach logical task/requirement references, never input or report paths."""
    public_tasks = {task.task_id: task for task in develop_tasks if not task.hidden_test}
    rows = []
    for row in candidate_feedback(feedback).tasks:
        if row['task_id'] not in public_tasks:
            continue
        task = public_tasks[row['task_id']]
        refs = [{'requirement_id':'original-task','description':task.instruction,
                 'source_ref':f'task:{task.task_id}'}]
        rows.append({**row, 'requirement_refs': refs,
                     'trace_summary': {'acceptance_status': row.get('acceptance_status'),
                                       'visible_issue_count': len(row.get('issues', row.get('errors', [])))}})
    return candidate_feedback(feedback.model_copy(update={'tasks': rows}))


def comparison_metrics(baseline, candidate, root, contract):
    splits = set(baseline)
    complete = bool(splits) and splits == set(candidate) and all(r.get("assessment_complete") and r.get("quality_score") is not None for bundle in (baseline, candidate) for r in bundle.values())
    identity_match=bool(splits) and splits==set(candidate) and all(baseline[s]["assessment_identity"] == candidate[s]["assessment_identity"] == contract.assessment_identity and baseline[s]["split_hash"] == candidate[s]["split_hash"]==contract.split_hashes[s] for s in splits)
    comparable = complete and identity_match
    task_comparable=identity_match and all(r.get('task_outcomes_complete',r.get('assessment_complete')) for bundle in (baseline,candidate) for r in bundle.values())
    metrics = {"assessment_mode": "artifact-v1", "assessment_complete": complete,
        "comparable": comparable, "repeat_agreement": complete and all(r.get("repeat_agreement") for bundle in (baseline, candidate) for r in bundle.values()),
        "evaluation_seconds": sum(r.get("evaluation_seconds", 0) for bundle in (baseline, candidate) for r in bundle.values()),
        "cost_delta": None, "critical_regressions": 0, "quality_delta": None, "success_delta": None,
        "protected_quality_deltas": {}, "issue_changes": {"resolved": 0, "introduced": 0},
        'task_comparable':task_comparable,'task_success_delta':None,'execution_success_delta':None,
        'paired_quality_delta':None,'paired_quality_denominators':{}}
    if not task_comparable:
        return metrics
    if "develop" not in splits:
        metrics["comparable"] = False
        return metrics
    # Compare the same admitted tasks, even if one version produced no artifact.
    private={}
    for split in splits:
        pairs=[]
        for side,bundle in [('baseline',baseline),('candidate',candidate)]:
            data=json.loads((Path(root)/side/split/'evaluation_full.json').read_text(encoding='utf-8'))
            rows=data['rows'];ids=[r['task_id'] for r in rows]
            report=bundle[split];denominator=report.get('task_denominator',report['task_count'])
            if (type(denominator) is not int or denominator<1 or len(ids)!=len(set(ids)) or len(ids)!=denominator
                or ('task_cohort_hash' in report and report['task_cohort_hash']!=canonical_json_hash(ids))):
                metrics.update(task_comparable=False,comparable=False)
                return metrics
            if 'task_outcomes_complete' in report:
                rates={'task_success_rate':sum(r.get('task_success') is True for r in rows)/denominator,
                       'execution_success_rate':sum(r.get('execution_success') is True for r in rows)/denominator}
                valid=all(r.get('task_outcome_complete') is True and type(r.get('task_success')) is bool
                    and r.get('execution_complete') is True and type(r.get('execution_success')) is bool for r in rows)
                valid=valid and all(type(report.get(k)) in {int,float} and math.isfinite(report[k])
                    and abs(report[k]-value)<1e-10 for k,value in rates.items())
                count=sum(r.get('assessment_complete') is True and type(r.get('score')) in {int,float}
                    and math.isfinite(r['score']) and 0<=r['score']<=1 for r in rows)
                valid=valid and type(report.get('quality_denominator')) is int and report['quality_denominator']==count
                valid=valid and report.get('success_rate')==report.get('task_success_rate')
                if not valid:
                    metrics.update(task_comparable=False,comparable=False)
                    return metrics
            pairs.append({r['task_id']:r for r in rows})
        if pairs[0].keys()!=pairs[1].keys():
            metrics.update(task_comparable=False,comparable=False)
            return metrics
        private[split]=pairs
    metrics['success_delta']=candidate['develop'].get('task_success_rate',candidate['develop']['success_rate'])-baseline['develop'].get('task_success_rate',baseline['develop']['success_rate'])
    metrics['task_success_delta']=metrics['success_delta']
    if all(bundle['develop'].get('execution_success_rate') is not None for bundle in [baseline,candidate]):
        metrics['execution_success_delta']=candidate['develop']['execution_success_rate']-baseline['develop']['execution_success_rate']
    if comparable:
        metrics["quality_delta"] = candidate["develop"]["quality_score"] - baseline["develop"]["quality_score"]
        metrics["protected_quality_deltas"] = {s: candidate[s]["quality_score"] - baseline[s]["quality_score"] for s in splits if s != "develop"}
    # Private rows remain on the evaluation side, including hidden requirements.
    for split in splits:
        old_rows,new_rows=private[split]
        eligible=[key for key in old_rows if old_rows[key].get('assessment_complete') and new_rows[key].get('assessment_complete')
            and old_rows[key].get('score') is not None and new_rows[key].get('score') is not None]
        metrics['paired_quality_denominators'][split]=len(eligible)
        if split=='develop' and eligible:
            metrics['paired_quality_delta']=sum(new_rows[k]['score']-old_rows[k]['score'] for k in eligible)/len(eligible)
        for row in new_rows.values():
            previous = old_rows[row["task_id"]]
            before = {c["requirement_id"]: c["status"] for c in (previous.get('score_report') or {}).get('criterion_results',[])}
            after = {c["requirement_id"]: c["status"] for c in (row.get('score_report') or {}).get('criterion_results',[])}
            metrics["critical_regressions"] += (int(previous.get('passed') is True and row.get('passed') is not True)
                if (row.get('score_report') or {}).get('score_semantics')=='llm-task-review-v1' else
                sum(before.get(r) == "PASS" and after.get(r) != "PASS" for r in row["critical_requirements"]))
            if not (row.get('assessment_complete') and previous.get('assessment_complete')):continue
            a = {i["issue_id"] for i in (previous.get('issue_report') or {}).get('issues',[]) if i["kind"] == "artifact_defect"}
            b = {i["issue_id"] for i in (row.get('issue_report') or {}).get('issues',[]) if i["kind"] == "artifact_defect"}
            metrics["issue_changes"]["resolved"] += len(a - b)
            metrics["issue_changes"]["introduced"] += len(b - a)
    return metrics


def decide_artifact(candidate_id, verification, metrics, contract):
    from .hashing import canonical_json_hash
    from .rsi_contracts import PromotionDecision

    t = contract.thresholds
    required = {"quality_gain", "success_tolerance", "protected_quality_tolerance", "max_evaluation_seconds"}
    if not required.issubset(t):
        raise ValueError("artifact-v1 needs explicitly versioned quality/success/protected/cost thresholds")
    gates = {
        "verification": verification.passed,
        "complete": metrics["assessment_complete"], "comparable": metrics["comparable"],
        "quality": metrics["quality_delta"] is not None and metrics["quality_delta"] > t["quality_gain"],
        "success": metrics["success_delta"] is not None and metrics["success_delta"] >= -t["success_tolerance"],
        "critical_regression": metrics["critical_regressions"] == 0,
        "protected_quality": all(v >= -t["protected_quality_tolerance"] for v in metrics["protected_quality_deltas"].values()),
        "observed_repeat_agreement": metrics["repeat_agreement"],
        "measured_evaluation_budget": metrics["evaluation_seconds"] <= t["max_evaluation_seconds"],
    }
    if contract.comparison_policy:
        statistical = metrics.get('statistical_comparison', {})
        gates['paired_family_comparison'] = statistical.get('eligible') is True
        # Stochastic execution is assessed through paired confidence intervals,
        # not by requiring identical outcomes in every independent execution.
        gates.pop('observed_repeat_agreement')
        uses_success = statistical.get('splits', {}).get('develop', {}).get('primary_metric') == 'task_success_rate'
        if uses_success:
            gates.pop('quality')
            gates.pop('complete')
            gates.pop('comparable')
            gates['complete_task_outcomes'] = metrics.get('task_comparable') is True
    return PromotionDecision(candidate_id=candidate_id, decision="accept" if all(gates.values()) else "reject", gate_results=gates,
        develop_delta=metrics["quality_delta"], cost_delta=None,
        evidence_refs=[canonical_json_hash({"verification": verification.model_dump(mode="json"), "metrics": metrics, "contract": contract.model_dump(mode="json"), "gates": gates})])
