#!/usr/bin/env python3
"""Initialize and inspect three video project records. Never call a provider."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

PROFILES = {'restaurant', 'factory', 'creative-ad', 'digital-human'}
KINDS = {'asset', 'storyboard', 'animatic', 'shot', 'audio', 'subtitle', 'edit', 'qc', 'delivery'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approved(record, digest):
    return (isinstance(record, dict) and record.get('sha256') == digest
            and bool(str(record.get('approved_by') or '').strip())
            and bool(str(record.get('user_evidence') or '').strip()))


def manifest(text):
    blocks = re.findall(r'^```json\s*\n(.*?)^```\s*$', text, re.M | re.S)
    if len(blocks) != 1:
        raise ValueError('TICKETS.md must contain exactly one fenced json manifest')
    data = json.loads(blocks[0])
    if not isinstance(data, dict) or not isinstance(data.get('tickets'), list):
        raise ValueError('manifest must be an object with tickets array')
    return data


def inspect(root, ready=False, required_ticket_ids=None):
    root = Path(root)
    errors = []
    for name in ('SPEC.md', 'TICKETS.md', 'STATE.json'):
        if not (root / name).is_file():
            errors.append('missing ' + name)
    if errors:
        return errors
    state = json.loads((root / 'STATE.json').read_text(encoding='utf-8'))
    if not isinstance(state, dict):
        return ['STATE.json must be object']
    if state.get('schema_version') != '0.1':
        errors.append('unsupported state schema_version')
    if state.get('profile') not in PROFILES:
        errors.append('invalid profile')
    for key, typ in [('approvals', dict), ('tickets', dict), ('assets', list), ('operations', list), ('budget', dict)]:
        if not isinstance(state.get(key), typ):
            errors.append('invalid STATE.' + key)
    if errors:
        return errors
    data = manifest((root / 'TICKETS.md').read_text(encoding='utf-8'))
    spec_hash, tickets_hash = sha(root / 'SPEC.md'), sha(root / 'TICKETS.md')
    if data.get('schema_version') != '0.1':
        errors.append('unsupported tickets schema_version')
    if data.get('tickets') and data.get('spec_sha256') != spec_hash:
        errors.append('manifest spec_sha256 is stale')
    if ready:
        for key, digest in [('spec', spec_hash), ('tickets', tickets_hash)]:
            if not approved(state['approvals'].get(key), digest):
                errors.append('missing/stale human approval: ' + key)
        if not data['tickets']:
            errors.append('no tickets')
    ids, tickets = set(), {}
    for ticket in data['tickets']:
        if not isinstance(ticket, dict):
            errors.append('ticket must be object')
            continue
        tid = ticket.get('id')
        if not isinstance(tid, str) or not tid.strip():
            errors.append('invalid ticket id')
            continue
        if tid in ids:
            errors.append('duplicate ticket ' + tid)
        ids.add(tid)
        tickets[tid] = ticket
        if ticket.get('kind') not in KINDS:
            errors.append('invalid kind: ' + tid)
        if ticket.get('source_mode') not in {'reuse', 'deterministic', 'generate'}:
            errors.append('invalid source_mode: ' + tid)
        if not isinstance(ticket.get('blocked_by'), list) or not all(isinstance(x, str) for x in ticket['blocked_by']):
            errors.append('invalid blocked_by: ' + tid)
        if not isinstance(ticket.get('acceptance'), list) or not ticket['acceptance'] or not all(isinstance(x, str) and x.strip() for x in ticket['acceptance']):
            errors.append('missing acceptance: ' + tid)
        if 'duration_s' in ticket:
            val = ticket['duration_s']
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
                errors.append('invalid duration_s: ' + tid)
        attempts = ticket.get('max_attempts', 2)
        if type(attempts) is not int or not 1 <= attempts <= 2:
            errors.append('max_attempts must be 1 or 2: ' + tid)
    visiting, visited = set(), set()

    def visit(tid):
        if tid in visiting:
            errors.append('dependency cycle at ' + tid)
            return
        if tid in visited:
            return
        visiting.add(tid)
        deps = tickets[tid].get('blocked_by', [])
        if not isinstance(deps, list):
            deps = []
        for dep in deps:
            if not isinstance(dep, str) or dep not in tickets:
                errors.append('missing blocker for ' + tid)
            else:
                visit(dep)
        visiting.remove(tid)
        visited.add(tid)
    for tid in tickets:
        visit(tid)
    operation_ids, operation_keys = set(), set()
    for op in state['operations']:
        if not isinstance(op, dict):
            errors.append('invalid operation record')
            continue
        for field, seen in [('operation_id', operation_ids), ('idempotency_key', operation_keys)]:
            val = op.get(field)
            if not isinstance(val, str) or not val.strip() or val in seen:
                errors.append('missing/duplicate operation ' + field)
            else:
                seen.add(val)
        if type(op.get('may_charge')) is not bool:
            errors.append('operation may_charge missing/invalid; reconcile charge uncertainty')
        if op.get('status') not in {'prepared','submitted','running','succeeded','failed','unknown','cancelled'}:
            errors.append('invalid operation status')
        if op.get('intent') == 'generate' and type(op.get('counts_as_attempt')) is not bool:
            errors.append('generation operation requires counts_as_attempt')
        if op.get('intent') == 'generate' and op.get('counts_as_attempt') is False and op.get('status') != 'prepared':
            cancelled_before_dispatch = (op.get('status') == 'cancelled'
                and op.get('submission_status') == 'not_sent'
                and op.get('actual_cost') == 0 and op.get('settlement_evidence'))
            if not cancelled_before_dispatch and not op.get('non_execution_evidence'):
                errors.append('excluding generation attempt requires non_execution_evidence')
    asset_ids, assets_by_id = set(), {}
    for asset in state['assets']:
        if not isinstance(asset, dict) or not isinstance(asset.get('id'), str) or not asset['id'].strip():
            errors.append('invalid asset record')
            continue
        aid = asset['id']
        if aid in asset_ids:
            errors.append('duplicate asset ' + aid)
        asset_ids.add(aid)
        assets_by_id[aid] = asset
        if asset.get('status') in {'approved', 'locked'} and not asset.get('local_path'):
            if not asset.get('media_id') or not asset.get('ref'):
                errors.append('approved remote asset needs stable media_id and recoverable ref ' + aid)
        if asset.get('local_path'):
            path = Path(asset['local_path'])
            if not path.is_absolute():
                path = root / path
            if not path.is_file():
                errors.append('missing local asset ' + aid)
            elif asset.get('sha256') and sha(path) != asset['sha256']:
                errors.append('changed local asset ' + aid)
            elif asset.get('status') in {'approved', 'locked'} and not asset.get('sha256'):
                errors.append('approved local asset requires sha256 ' + aid)
    for tid, ticket in tickets.items():
        refs = ticket.get('asset_ids', [])
        if not isinstance(refs, list) or not all(isinstance(aid, str) for aid in refs):
            errors.append('invalid asset_ids in ' + tid)
            continue
        for aid in refs:
            if aid not in asset_ids:
                errors.append('missing asset reference ' + str(aid) + ' in ' + tid)
            elif ready and (required_ticket_ids is None or tid in required_ticket_ids):
                asset = assets_by_id[aid]
                if asset.get('status') not in {'approved', 'locked'}:
                    errors.append('unapproved required asset ' + aid)
                binding = state['approvals'].get('spec', {}).get('asset_bindings', {}).get(aid)
                current = {k:asset.get(k) for k in ('sha256', 'media_id', 'ref')}
                if binding != current:
                    errors.append('asset differs from human-approved binding ' + aid)
    return errors


def init(root, profile):
    root = Path(root)
    if profile not in PROFILES:
        raise ValueError('invalid profile')
    root.mkdir(parents=True, exist_ok=True)
    paths = [root / n for n in ('SPEC.md', 'TICKETS.md', 'STATE.json')]
    if any(p.exists() for p in paths):
        raise ValueError('refusing to overwrite existing project records')
    paths[0].write_text('# 视频制作规格（草稿）\n\n待讨论目标、素材与分镜；未批准。\n', encoding='utf-8')
    tickets = {'schema_version': '0.1', 'spec_sha256': sha(paths[0]), 'tickets': []}
    paths[1].write_text('# 视频任务（草稿）\n\n```json\n' + json.dumps(tickets, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    state = {'schema_version': '0.1', 'profile': profile, 'stage': 'setup',
             'project_id': None, 'revision_token': None, 'capabilities': {},
             'approvals': {}, 'assets': [], 'tickets': {}, 'operations': [],
             'budget': {'approved_by': None, 'user_evidence': None, 'unit': None,
                        'limit': 0, 'spent': 0, 'reserved': 0,
                        'max_generation_calls': 0, 'generation_calls_used': 0,
                        'allowed_ticket_ids': [], 'spec_sha256': None, 'tickets_sha256': None}}
    paths[2].write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('init')
    p.add_argument('project')
    p.add_argument('--profile', choices=sorted(PROFILES), default='restaurant')
    p = subs.add_parser('check')
    p.add_argument('project')
    p.add_argument('--ready', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            init(args.project, args.profile)
            errors = inspect(args.project)
        else:
            errors = inspect(args.project, args.ready)
        print(json.dumps({'ok': not errors, 'errors': errors, 'scope': 'local_records_only'}, ensure_ascii=False))
        return 1 if errors else 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'ok': False, 'errors': [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
