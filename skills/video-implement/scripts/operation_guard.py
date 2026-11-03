#!/usr/bin/env python3
"""Read-only local preflight. Does not call APIs, authenticate approvals or reserve funds."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from project_files import inspect


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def has_run(value):
    if isinstance(value, dict):
        return value.get('run') is True or any(has_run(v) for v in value.values())
    return isinstance(value, list) and any(has_run(v) for v in value)


def check(state_path, plan):
    root = Path(state_path).parent
    state = json.loads(Path(state_path).read_text(encoding='utf-8'))
    errors = inspect(root, ready=True, required_ticket_ids={plan.get('ticket_id')})
    if not isinstance(state, dict) or not isinstance(plan, dict):
        return ['state and plan must be objects']
    if state.get('schema_version') != '0.1':
        errors.append('unsupported state schema')
    for field in ('operation_id', 'ticket_id', 'intent', 'idempotency_key'):
        if not isinstance(plan.get(field), str) or not plan[field].strip() or plan[field].startswith('REPLACE_'):
            errors.append('missing plan.' + field)
    request = plan.get('request')
    if not isinstance(request, dict) or not request:
        errors.append('request must be nonempty object from actual schema')
    elif plan.get('payload_sha256') != canonical(request):
        errors.append('payload hash mismatch')
    if plan.get('project_id') != state.get('project_id') or not state.get('project_id'):
        errors.append('project mismatch or missing project_id')
    if not state.get('revision_token') or plan.get('expected_revision') != state['revision_token']:
        errors.append('expected_revision must equal project revision_token')
    spec_hash, ticket_hash = digest(root / 'SPEC.md'), digest(root / 'TICKETS.md')
    approvals = state.get('approvals', {})
    for key, value in [('spec', spec_hash), ('tickets', ticket_hash)]:
        a = approvals.get(key, {})
        if a.get('sha256') != value or not a.get('approved_by') or not a.get('user_evidence'):
            errors.append('missing/stale human approval: ' + key)
    blocks = re.findall(r'^```json\s*\n(.*?)^```\s*$', (root / 'TICKETS.md').read_text(encoding='utf-8'), re.M | re.S)
    if len(blocks) != 1:
        return errors + ['exactly one tickets manifest required']
    data = json.loads(blocks[0])
    if data.get('spec_sha256') != spec_hash:
        errors.append('stale tickets spec hash')
    matches = [t for t in data.get('tickets', []) if t.get('id') == plan.get('ticket_id')]
    if len(matches) != 1:
        errors.append('ticket must exist exactly once')
    else:
        for dep in matches[0].get('blocked_by', []):
            if state.get('tickets', {}).get(dep, {}).get('status') != 'succeeded':
                errors.append('blocker not succeeded: ' + dep)
    ops = state.get('operations', [])
    for op in ops:
        if op.get('operation_id') == plan.get('operation_id') or op.get('idempotency_key') == plan.get('idempotency_key'):
            errors.append('operation/key already exists: reconcile instead of new submission')
    def check_request_fields(value):
        if isinstance(value, dict):
            for key, expected in [('projectId', plan.get('project_id')),
                                  ('expectedRevision', plan.get('expected_revision')),
                                  ('idempotencyKey', plan.get('idempotency_key'))]:
                if key in value and value[key] != expected:
                    errors.append('request ' + key + ' differs from plan')
            for child in value.values():
                check_request_fields(child)
        elif isinstance(value, list):
            for child in value:
                check_request_fields(child)
    check_request_fields(request)
    charge = plan.get('may_charge')
    if type(charge) is not bool:
        errors.append('may_charge must be explicit boolean')
    if has_run(request) and charge is not True:
        errors.append('run=true cannot be classified non-charging')
    if plan.get('intent') in {'generate', 'render', 'export'} and charge is not True:
        errors.append('generation/render/export requires cost preflight even if quoted free')
    cost = plan.get('cost_upper_bound')
    if not number(cost):
        errors.append('finite nonnegative cost_upper_bound required')
    if charge is False and cost != 0:
        errors.append('non-charging operation must have zero cost upper bound')
    if charge is True:
        budget = state.get('budget', {})
        if not budget.get('approved_by') or not budget.get('user_evidence'):
            errors.append('human budget approval required')
        if budget.get('spec_sha256') != spec_hash or budget.get('tickets_sha256') != ticket_hash:
            errors.append('budget approval bound to stale/missing spec or tickets')
        if not budget.get('unit') or budget.get('unit') != plan.get('cost_unit'):
            errors.append('cost unit mismatch/unknown')
        if not plan.get('cost_evidence'):
            errors.append('verified quote/free evidence required')
        if plan.get('ticket_id') not in budget.get('allowed_ticket_ids', []):
            errors.append('ticket outside approved spend scope')
        vals = [budget.get(k) for k in ('limit', 'spent', 'reserved')]
        if not all(number(v) for v in vals):
            errors.append('invalid budget numeric fields')
        elif number(cost) and budget['spent'] + budget['reserved'] + cost > budget['limit']:
            errors.append('budget upper bound exceeded')
        cap, used = budget.get('max_generation_calls'), budget.get('generation_calls_used')
        if type(cap) is not int or type(used) is not int or used < 0 or cap < 1 or used >= cap:
            errors.append('generation call ceiling reached/invalid')
        charged = [o for o in ops if o.get('may_charge') is True]
        called = [o for o in charged if not (
            o.get('status') == 'cancelled' and o.get('counts_as_attempt') is False
            and o.get('submission_status') == 'not_sent'
            and o.get('actual_cost') == 0 and o.get('settlement_evidence'))]
        if type(used) is int and used < len(called):
            errors.append('budget generation_calls_used lags operation ledger')
        ledger_spent, ledger_reserved = 0, 0
        for op in charged:
            if not number(op.get('cost_upper_bound')) or op.get('cost_unit') != budget.get('unit'):
                errors.append('operation cost upper bound/unit unknown: reconcile ledger')
                continue
            actual = op.get('actual_cost')
            if actual is not None:
                if not number(actual) or not op.get('settlement_evidence'):
                    errors.append('operation settlement lacks actual cost/evidence')
                else:
                    ledger_spent += actual
            else:
                ledger_reserved += op['cost_upper_bound']
        if all(number(v) for v in vals):
            if budget['spent'] < ledger_spent or budget['reserved'] < ledger_reserved:
                errors.append('budget aggregate lags unsettled/settled operation costs')
        pending = [o for o in ops if o.get('may_charge') is True and o.get('status') in {'prepared', 'submitted', 'running', 'unknown'}]
        if pending:
            errors.append('unsettled charging operation: reconcile before spending again')
        if plan.get('intent') == 'generate' and len(matches) == 1:
            attempts = [o for o in ops if o.get('ticket_id') == plan.get('ticket_id')
                        and o.get('intent') == 'generate'
                        and o.get('counts_as_attempt', True)
                        and o.get('status') in {'submitted', 'running', 'succeeded', 'failed', 'unknown', 'cancelled'}]
            if len(attempts) >= matches[0].get('max_attempts', 2):
                errors.append('ticket attempt ceiling reached; reopen upstream decision')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state')
    parser.add_argument('plan')
    args = parser.parse_args()
    try:
        errors = check(args.state, json.loads(Path(args.plan).read_text(encoding='utf-8')))
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        errors = [str(exc)]
    print(json.dumps({'ok': not errors, 'errors': errors, 'scope': 'advisory_local_preflight_only'}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
