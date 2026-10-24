"""Serialized live CLI budget for authored qualification, not production T31.

Approval is an explicit input. Reservations survive interruption. This helper
never changes global Codex configuration or reads credential contents.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

from workagent_rsi.hashing import sha256_file
from workagent_rsi.model_judgement import _run_cli
from workagent_rsi.run_contracts import LiveCallPolicy


class QualificationCLI:
    def __init__(self, policy_path, *, runner=None):
        self.path=Path(policy_path).resolve(strict=True)
        self.policy=LiveCallPolicy.model_validate_json(self.path.read_text(encoding='utf-8'))
        self.policy.require_authorized(provider='codex-cli',model='gpt-6.1-sol',endpoint=None)
        self.runner=runner or _run_cli
        self.state_path=self.path.with_name('budget-state.json')

    def __call__(self, command, cwd, timeout, prompt):
        # A single owner holds the lock for the whole call. An interrupted owner
        # leaves a reservation and lock; resumption requires reviewing that call.
        lock=self.path.with_name('budget.lock')
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.close(descriptor)
        started=time.monotonic()
        try:
            policy_hash=sha256_file(self.path)
            state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {
                'policy_sha256':policy_hash,'calls':[],'reserved_wall_seconds':0,'actual_tool_calls':0}
            if state['policy_sha256']!=policy_hash:raise ValueError('approved policy changed after reservation')
            if state.get('quarantined'):raise ValueError('unexpected prior tool activity; qualification quarantined')
            if len(state['calls'])>=self.policy.max_model_calls:raise ValueError('approved request budget exhausted')
            remaining=self.policy.max_wall_seconds-state['reserved_wall_seconds']
            if remaining<1:raise ValueError('approved cumulative wall budget exhausted')
            timeout=min(timeout,remaining)
            if command[command.index('--model')+1]!=self.policy.model:raise ValueError('unapproved model')
            command=list(command)
            # No automatic transport retries, no optional model tools.
            # Built-in provider IDs cannot be overridden in this CLI version.
            # This per-invocation alias retains normal OpenAI account auth and
            # its default endpoint; it only supplies explicit retry limits.
            command[-1:-1]=['-c','model_provider="wrsi_qualification"',
                '-c','model_providers.wrsi_qualification={name="OpenAI qualification", requires_openai_auth=true, wire_api="responses", request_max_retries=0, stream_max_retries=0, supports_websockets=true}']
            call={'index':len(state['calls'])+1,'started_at':datetime.now(timezone.utc).isoformat(),
                  'status':'reserved','timeout_seconds':timeout,'argv':command,
                  'prompt_sha256':__import__('hashlib').sha256(prompt.encode('utf-8')).hexdigest()}
            state['calls'].append(call)
            state['reserved_wall_seconds']+=timeout
            self._save(state)
            try:
                result=self.runner(command,cwd,timeout,prompt+'\nKeep the response below 4096 output tokens. Use no tools.')
                if '--output-last-message' in command:
                    evidence=Path(command[command.index('--output-last-message')+1]).parent
                    (evidence/'runner-stdout.jsonl').write_text(result.stdout or '',encoding='utf-8')
                    (evidence/'runner-stderr.txt').write_text(result.stderr or '',encoding='utf-8')
                events=[]
                for line in (result.stdout or '').splitlines():
                    try:events.append(json.loads(line))
                    except ValueError:pass
                items=[e.get('item',{}) for e in events if e.get('type')=='item.completed']
                # Protocol status/plan items are not proof of a tool request.
                # Keep every event so protocol changes are inspectable.
                tool_types={'command_execution','file_change','mcp_tool_call','web_search','collab_tool_call','tool_call'}
                tools=[i for i in items if i.get('type') in tool_types]
                call.update(status='completed',exit_code=result.returncode,tool_calls=len(tools),
                    item_types=[i.get('type') for i in items],
                    usage=[e.get('usage') for e in events if e.get('type')=='turn.completed'])
                state['actual_tool_calls']+=len(tools)
                if tools:
                    state['quarantined']=True
                    raise ValueError('qualification invoked an unexpected tool; result rejected')
                return result
            except BaseException as exc:
                call.update(status='failed',error_type=type(exc).__name__)
                raise
            finally:
                elapsed=time.monotonic()-started
                call.update(ended_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=elapsed)
                # Retain the full reservation for failed/unknown calls; never
                # automatically reclaim possibly consumed external work.
                if call['status']=='completed':
                    state['reserved_wall_seconds']-=max(0,timeout-min(timeout,math.ceil(elapsed)))
                self._save(state)
        finally:
            lock.unlink()

    def _save(self,state):
        temporary=self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
        temporary.replace(self.state_path)
