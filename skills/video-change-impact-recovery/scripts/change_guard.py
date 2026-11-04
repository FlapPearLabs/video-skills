#!/usr/bin/env python3
"""Offline, fail-closed change-impact planner/verifier. NOT a NodeTool API client.

The JSON schema is a normalized *projection* produced by the agent after reading the
live NodeTool timeline, not the native NodeTool TimelineDocument.

Stdlib only. All time values are integer milliseconds.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

KINDS = {"shot", "voice", "subtitle", "music", "sfx", "transition", "beat", "overlay", "export"}
FIELDS = {"id", "kind", "shot_id", "start_ms", "duration_ms", "asset_ref", "asset_hash", "deps", "sync", "locked", "metadata"}
SAFE_META = {"note", "source"}


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def content_digest(doc):
    """Ignore the server's changing read/version token when checking edit content."""
    return digest({k: v for k, v in doc.items() if k != "revision"})


def fail(msg):
    raise ValueError(msg)


def _node_map(doc):
    if not isinstance(doc, dict) or doc.get("schema_version") != "1.0" or not isinstance(doc.get("objects"), list):
        fail("invalid normalized manifest: expected schema_version=1.0 and objects array")
    if not isinstance(doc.get("timeline_id"), str) or not doc["timeline_id"].strip():
        fail("timeline_id required")
    nodes = {}
    for x in doc["objects"]:
        if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not x["id"]:
            fail("each object needs nonempty id")
        if set(x) - FIELDS:
            fail(f"unknown fields on {x['id']}: {sorted(set(x)-FIELDS)}")
        k = x.get("kind")
        if k not in KINDS:
            fail(f"unknown kind on {x['id']}: {k}")
        if x["id"] in nodes:
            fail(f"duplicate id: {x['id']}")
        if type(x.get("start_ms")) is not int or x["start_ms"] < 0:
            fail(f"bad start_ms: {x['id']}")
        if type(x.get("duration_ms")) is not int or x["duration_ms"] <= 0:
            fail(f"bad duration_ms: {x['id']}")
        if not isinstance(x.get("deps", []), list) or not all(isinstance(d, str) for d in x.get("deps", [])):
            fail(f"bad deps: {x['id']}")
        if type(x.get("locked", False)) is not bool:
            fail(f"bad locked: {x['id']}")
        nodes[x["id"]] = x
    adj = {k: set() for k in nodes}
    for x in nodes.values():
        for d in x.get("deps", []):
            if d not in nodes:
                fail(f"unknown dependency {d} on {x['id']}")
            adj[d].add(x["id"])
        sync = x.get("sync")
        if sync is not None:
            if not isinstance(sync, dict) or set(sync) != {"to", "point", "offset_ms"}:
                fail(f"bad sync contract on {x['id']}")
            if sync["to"] not in nodes or sync["to"] == x["id"] or sync["point"] not in ("start", "end") or type(sync["offset_ms"]) is not int:
                fail(f"invalid sync target/point/offset on {x['id']}")
            if sync["to"] not in x.get("deps", []):
                fail(f"sync target missing from deps on {x['id']}")
    colors = {}
    def dfs(n):
        if colors.get(n) == 1:
            fail(f"dependency cycle at {n}")
        if colors.get(n) == 2:
            return
        colors[n] = 1
        for next_id in adj[n]:
            dfs(next_id)
        colors[n] = 2
    for k in nodes:
        dfs(k)
    for x in nodes.values():
        if x.get("sync"):
            sync = x["sync"]
            parent = nodes[sync["to"]]
            expected = parent["start_ms"] + (parent["duration_ms"] if sync["point"] == "end" else 0) + sync["offset_ms"]
            if x["start_ms"] != expected:
                fail(f"sync drift {x['id']}: expected {expected}, got {x['start_ms']}")
    return nodes, adj


def _closure(adj, start):
    seen, todo = set(), [start]
    while todo:
        n = todo.pop()
        for child in adj[n]:
            if child not in seen:
                seen.add(child)
                todo.append(child)
    return seen


def _diff(a, b):
    old, new = _node_map(a)[0], _node_map(b)[0]
    changed = {}
    for oid in sorted(set(old) | set(new)):
        if oid not in old or oid not in new:
            changed[oid] = ["__exists__"]
        else:
            fields = [f for f in set(old[oid]) | set(new[oid]) if old[oid].get(f) != new[oid].get(f)]
            if fields:
                changed[oid] = sorted(fields)
    return changed


def _reanchor(nodes):
    """Propagate only explicitly declared sync constraints, topologically."""
    pending = {i for i, n in nodes.items() if n.get("sync")}
    while pending:
        ready = [i for i in pending if nodes[i]["sync"]["to"] not in pending]
        if not ready:
            fail("sync cycle")
        for i in ready:
            n = nodes[i]
            s = n["sync"]
            parent = nodes[s["to"]]
            n["start_ms"] = parent["start_ms"] + (parent["duration_ms"] if s["point"] == "end" else 0) + s["offset_ms"]
            pending.remove(i)


def build_plan(before, intent):
    nodes, adj = _node_map(before)
    if not isinstance(intent, dict) or intent.get("type") not in ("replace_media", "change_duration", "change_transition"):
        fail("intent.type must be replace_media/change_duration/change_transition")
    target = intent.get("target")
    if target not in nodes:
        fail(f"unknown target: {target}")
    old = nodes[target]
    if old.get("locked"):
        fail(f"target locked: {target}")
    planned = copy.deepcopy(before)
    after = {x["id"]: x for x in planned["objects"]}
    change_type = intent["type"]
    hard_blockers, warnings = [], []
    if change_type == "replace_media":
        if old["kind"] != "shot":
            fail("replace_media only accepts shot objects")
        asset = intent.get("asset_ref")
        if not isinstance(asset, str) or not asset:
            fail("asset_ref required")
        after[target]["asset_ref"] = asset
        if "asset_hash" in intent:
            h = intent["asset_hash"]
            if not isinstance(h, str) or not h:
                fail("nonempty asset_hash required when supplied")
            after[target]["asset_hash"] = h
        warnings.append("替换源视频后，原追踪/智能重构图/口型适配可能过期；需要重新检查实际画面")
    elif change_type == "change_duration":
        if old["kind"] != "shot":
            fail("change_duration only accepts shot objects")
        length = intent.get("new_duration_ms")
        if type(length) is not int or length <= 0:
            fail("new_duration_ms must be positive integer")
        delta = length - old["duration_ms"]
        after[target]["duration_ms"] = length
        # Fail closed if any next shot intersects the old target or timeline structure is ambiguous.
        shots = sorted((n for n in nodes.values() if n["kind"] == "shot"), key=lambda n: (n["start_ms"], n["id"]))
        for prev, nxt in zip(shots, shots[1:]):
            if prev["start_ms"] + prev["duration_ms"] > nxt["start_ms"]:
                hard_blockers.append("镜头重叠或多路并行：不能自动 ripple，须先确定主视频轨")
                break
        boundary = old["start_ms"] + old["duration_ms"]
        for s in shots:
            if s["id"] != target and s["start_ms"] >= boundary:
                if s.get("locked") and delta:
                    hard_blockers.append(f"后续锁定镜头阻止 ripple: {s['id']}")
                else:
                    after[s["id"]]["start_ms"] += delta
        if delta:
            for n in nodes.values():
                if n["kind"] in {"voice", "subtitle", "sfx"} and not n.get("sync") and n["start_ms"] >= boundary:
                    hard_blockers.append(f"未绑定后续音画对象 {n['id']}：先建立真实时间锚点，不得自动 ripple")
        warnings.append("BGM 节拍不因镜头位移自动重排；如有高潮卡点，必须试听或重配节奏")
        warnings.append("时长扩展后需检查音乐结尾、字幕时长、镜头边界及导出总时长")
    else:
        if old["kind"] != "transition":
            fail("change_transition requires a transition object")
        asset = intent.get("asset_ref")
        if not isinstance(asset, str) or not asset:
            fail("asset_ref required")
        after[target]["asset_ref"] = asset
    _reanchor(after)
    # Cannot mutate a locked dependent object, even if auto-sync calls for it.
    if not hard_blockers:
        for oid, fields in _diff(before, planned).items():
            if nodes[oid].get("locked"):
                hard_blockers.append(f"locked dependent changed: {oid} {fields}")
    impact = _closure(adj, target)
    changed = _diff(before, planned)
    allowed_fields = {oid: fields for oid, fields in changed.items()}
    # A coarse timing-risk scan complements, but does not replace, semantic AV checking.
    if change_type == "change_duration":
        for n in nodes.values():
            if n["kind"] in {"voice", "subtitle", "sfx", "beat", "music"} and not n.get("sync"):
                warnings.append(f"未绑定时间锚点: {n['id']}，不得自动声称同步完成")
    if any(nodes[x].get("locked") for x in impact):
        warnings.append("依赖闭包中包含锁定对象；只能检查，不能修改")
    return {
        "schema_version": "1.0", "timeline_id": before["timeline_id"], "base_sha256": digest(before),
        "intent": intent, "target": target, "change_type": change_type,
        "impact_ids": sorted(impact | {target}), "check_only_ids": sorted((impact | {target}) - set(changed)),
        "allowed_fields": allowed_fields, "predicted_changes": changed,
        "candidate": planned, "blockers": sorted(set(hard_blockers)),
        "warnings": sorted(set(warnings)), "ready_for_write": not bool(hard_blockers),
        "safety": {"node_tool_write_performed": False, "media_audited": False, "visual_audio_verified": False},
    }


def verify(before, after, plan):
    """Strict field diff + sync invariants; media review is always a separate gate."""
    errors = []
    if digest(before) != plan.get("base_sha256"):
        errors.append("stale base / plan hash mismatch")
    if before.get("timeline_id") != after.get("timeline_id") or before.get("timeline_id") != plan.get("timeline_id"):
        errors.append("timeline_id mismatch")
    if plan.get("blockers") or not plan.get("ready_for_write"):
        errors.append("plan blocked; no write allowed")
    try:
        _node_map(before)
        _node_map(after)
        delta = _diff(before, after)
    except ValueError as e:
        return {"structural_ok": False, "scope_ok": False, "passed": False, "errors": errors + [str(e)], "changes": {}}
    if set(_node_map(before)[0]) != set(_node_map(after)[0]):
        errors.append("object added/deleted; outside v1 scope")
    allowed = plan.get("allowed_fields", {})
    for oid, fs in delta.items():
        for f in fs:
            if f not in allowed.get(oid, []):
                errors.append(f"unapproved change: {oid}.{f}")
    # Allowed diffs must equal the deterministic plan's candidate (never merely subset).
    if content_digest(after) != content_digest(plan.get("candidate", {})):
        errors.append("actual document differs from planned candidate (excluding revision)")
    for oid, orig in _node_map(before)[0].items():
        if orig.get("locked") and orig != _node_map(after)[0].get(oid):
            errors.append(f"locked object changed: {oid}")
    # Structural validation is only schema+sync. NodeTool still must validate its native document.
    return {
        "structural_ok": not any("sync" in e or "bad" in e for e in errors),
        "scope_ok": not errors, "passed": not errors, "errors": errors,
        "changes": delta, "av_review_required": True,
        "nodetool_validate_required": True, "render_required": True,
        "production_committable": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe offline impact planning and verification (not NodeTool native)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("inspect", "plan", "verify"):
        p = sub.add_parser(name)
        p.add_argument("before", type=Path)
        if name == "plan":
            p.add_argument("intent", type=Path)
        if name == "verify":
            p.add_argument("after", type=Path)
            p.add_argument("plan", type=Path)
        p.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        before = json.loads(args.before.read_text(encoding="utf-8"))
        if args.cmd == "inspect":
            nodes, deps = _node_map(before)
            result = {"valid": True, "timeline_id": before["timeline_id"], "object_count": len(nodes), "manifest_sha256": digest(before)}
        elif args.cmd == "plan":
            intent = json.loads(args.intent.read_text(encoding="utf-8"))
            result = build_plan(before, intent)
        else:
            after = json.loads(args.after.read_text(encoding="utf-8"))
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            result = verify(before, after, plan)
        output = json.dumps(result, indent=2, ensure_ascii=False)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        if args.cmd == "plan" and not result["ready_for_write"]:
            return 2
        if args.cmd == "verify" and not result["passed"]:
            return 2
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
