"""Shared reservations for execution, assessment and retries in one run/cohort."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import threading
import time

from pydantic import BaseModel, ConfigDict, Field


class BudgetExceeded(RuntimeError):
    pass


class _Limits(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, allow_inf_nan=False)
    max_model_calls: int = Field(default=24, ge=0)
    max_tool_calls: int = Field(default=64, ge=0)
    max_repairs: int = Field(default=2, ge=0)
    max_wall_seconds: float = Field(default=600, gt=0)
    max_cost_usd: float | None = Field(default=None, gt=0)


_active = ContextVar('workagent_run_budget', default=None)
_deadline = ContextVar('workagent_budget_deadline', default=None)


class RunBudget:
    """A launched request stays charged even when it fails or is interrupted.

    Unknown actual monetary cost retains its reservation. Cost-limited calls
    require a known conservative upper bound before launch. This is a runtime
    counter, not authorization to make a live model request.
    """
    def __init__(self, *, clock=time.monotonic, **limits):
        self.limits = _Limits(**limits)
        self.clock = clock
        self.started = clock()
        self.used = {'model':0, 'tool':0, 'repair':0}
        self.entries = []
        self.cost_reserved = 0.0
        self.violations = []
        self._paths = set()
        self._lock = threading.RLock()

    def remaining_seconds(self):
        remaining=self.limits.max_wall_seconds-(self.clock()-self.started)
        if _active.get() is self and _deadline.get() is not None:
            remaining=min(remaining, _deadline.get()-self.clock())
        return max(0.0,remaining)

    @classmethod
    def from_ledger(cls, path, *, expected_limits=None, clock=time.monotonic):
        """Resume charged and interrupted reservations without replenishing caps.

        Prior active wall time is charged; time spent while the process was
        stopped is excluded. An interrupted reservation remains charged.
        """
        import json
        import math
        from pathlib import Path
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        limits = _Limits.model_validate(data['limits'])
        if data.get('schema_version') != 'run-budget-v1' or (expected_limits is not None and limits.model_dump() != expected_limits):
            raise ValueError('budget policy identity changed')
        result = cls(clock=clock, **limits.model_dump())
        entries = data['entries']
        used = {k:0 for k in result.used}
        for index, entry in enumerate(entries):
            if entry['ticket'] != index or entry['kind'] not in used or entry['status'] not in {'reserved','charged'}:
                raise ValueError('invalid budget reservation history')
            used[entry['kind']] += 1
        elapsed, cost = data['wall_seconds'], data['cost_reserved_usd']
        if used != data['used'] or any(type(v) not in {int,float} or not math.isfinite(v) or v < 0 for v in (elapsed,cost)):
            raise ValueError('invalid budget counters')
        for kind, maximum in [('model',limits.max_model_calls),('tool',limits.max_tool_calls),('repair',limits.max_repairs)]:
            if used[kind] > maximum:
                raise ValueError('budget history exceeds policy')
        result.started = clock()-elapsed
        result.used, result.entries, result.cost_reserved = used, entries, cost
        result.violations = list(data['violations'])
        return result

    def check(self):
        if self.violations or self.remaining_seconds() <= 0:
            raise BudgetExceeded('run budget deadline or accounting violation')

    def reserve(self, kind, *, cost_upper_bound=None):
        with self._lock:
            self.check()
            if kind not in self.used:
                raise ValueError('unknown budget reservation kind')
            maximum = getattr(self.limits, {'model':'max_model_calls','tool':'max_tool_calls','repair':'max_repairs'}[kind])
            if self.used[kind] >= maximum:
                raise BudgetExceeded(f'{kind} budget exhausted')
            if cost_upper_bound is not None:
                import math
                if isinstance(cost_upper_bound, bool) or not isinstance(cost_upper_bound,(int,float)) or not math.isfinite(cost_upper_bound) or cost_upper_bound<0:
                    raise ValueError('cost upper bound must be finite and nonnegative')
            if self.limits.max_cost_usd is not None:
                if kind=='model' and cost_upper_bound is None:
                    raise BudgetExceeded('cost budget requires a known upper bound before calling model')
                if self.cost_reserved+(cost_upper_bound or 0) > self.limits.max_cost_usd+1e-12:
                    raise BudgetExceeded('monetary budget exhausted')
            self.used[kind] += 1
            self.cost_reserved += cost_upper_bound or 0
            ticket = len(self.entries)
            self.entries.append({'ticket':ticket, 'kind':kind, 'status':'reserved',
                                 'reserved_at_seconds':max(0,self.clock()-self.started),
                                 'cost_upper_bound_usd':cost_upper_bound, 'actual_cost_usd':None})
            self._save()
            return ticket

    def reconcile(self, ticket, *, actual_cost_usd=None):
        with self._lock:
            entry = self.entries[ticket]
            if entry['status']!='reserved':
                raise ValueError('reservation already reconciled')
            if actual_cost_usd is not None:
                import math
                if isinstance(actual_cost_usd,bool) or not isinstance(actual_cost_usd,(int,float)) or not math.isfinite(actual_cost_usd) or actual_cost_usd<0:
                    raise ValueError('actual cost must be finite and nonnegative')
                bound=entry['cost_upper_bound_usd']
                if bound is not None and actual_cost_usd>bound+1e-12:
                    self.violations.append('actual cost exceeded reserved bound')
                self.cost_reserved += actual_cost_usd-(bound or 0)
            entry.update(status='charged', actual_cost_usd=actual_cost_usd)
            entry['reconciled_at_seconds']=max(0,self.clock()-self.started)
            self._save()
            if self.violations:
                raise BudgetExceeded(self.violations[-1])

    def snapshot(self):
        with self._lock:
            return {'schema_version':'run-budget-v1', 'limits':self.limits.model_dump(mode='json'),
                    'used':dict(self.used), 'wall_seconds':max(0,self.clock()-self.started),
                    'remaining_seconds':self.remaining_seconds(), 'cost_reserved_usd':self.cost_reserved,
                    'cost_known':all(e['actual_cost_usd'] is not None for e in self.entries if e['kind']=='model'),
                    'entries':[dict(e) for e in self.entries], 'violations':list(self.violations)}

    def _save(self):
        from .repair_loop import write_record
        for path in self._paths:
            write_record(path,self.snapshot())

    @contextmanager
    def activate(self, ledger=None, *, wall_seconds=None):
        if ledger is not None:
            from pathlib import Path
            with self._lock:
                self._paths.add(Path(ledger)); self._save()
        previous=_deadline.get() if _active.get() is self else None
        limit=self.clock()+wall_seconds if wall_seconds is not None else previous
        if previous is not None and limit is not None:limit=min(previous,limit)
        token=_active.set(self)
        deadline_token=_deadline.set(limit)
        try:
            yield self
        finally:
            _deadline.reset(deadline_token)
            _active.reset(token)
            with self._lock: self._save()


def active_budget():
    return _active.get()


@contextmanager
def budgeted_urlopen(opener, request, *, timeout):
    with budgeted_call('model') as remaining:
        with opener(request, timeout=min(timeout,remaining)) as response:
            yield response


@contextmanager
def budgeted_call(kind):
    budget = active_budget()
    ticket = budget.reserve(kind) if budget is not None else None
    try:
        yield budget.remaining_seconds() if budget is not None else float('inf')
    finally:
        if ticket is not None:
            budget.reconcile(ticket)
            budget.check()


def budgeted_tool(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with budgeted_call('tool') as remaining:
            if remaining!=float('inf'):
                # Native tool execution never receives more than the shared
                # remaining wall time, including a fractional final second.
                if remaining<1:
                    raise BudgetExceeded('less than one second remains for a native tool')
                kwargs['timeout_seconds']=min(kwargs.get('timeout_seconds',remaining), int(remaining))
            return function(*args, **kwargs)
    return wrapped
