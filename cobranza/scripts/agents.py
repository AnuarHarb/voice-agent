"""Agents as code for the collections agent: one template, one agent per fintech.

    uv run --project backend python scripts/agents.py build          # render + validate, offline
    uv run --project backend python scripts/agents.py push           # secrets, tools, KB, tests, agent, procedures, publish
    uv run --project backend python scripts/agents.py test [--llm gpt-6-luna]
    uv run --project backend python scripts/agents.py chat --tenant avanza   # real text conversation, real tools
    uv run --project backend python scripts/agents.py voices         # Colombian Spanish female voices
    uv run --project backend python scripts/agents.py status

The ElevenLabs CLI (`npx elevenlabs agents test <agent_id>`) works on the agents this pushes. This
script exists because procedures, workspace secrets and per-tenant tool sets are not covered by
`elevenlabs agents push`.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
STATE_FILE = ROOT / "deploy_state.json"
TENANTS = ["avanza", "nexo"]
PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")


def load_env() -> dict:
    env: dict = {}
    for path in (ROOT / "backend" / ".env", ROOT / ".env"):
        if path.exists():
            env.update({k: v for k, v in dotenv_values(path).items() if v})
    env.update({k: v for k, v in os.environ.items() if v})
    return env


ENV = load_env()
SESSION_VAR = ENV.get("SESSION_TOKEN_VAR", "secret__session_token")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ rendering

class Unresolved(Exception):
    pass


def resolve(token: str, ctx: dict):
    kind, _, rest = token.partition(":")
    if kind == "env":
        name, _, default = rest.partition(":")
        value = ENV.get(name) or default
        if not value:
            raise Unresolved(token)
        return value
    if kind == "file":
        return render((ROOT / rest).read_text(encoding="utf-8"), ctx)
    if kind in ("tool", "procedure", "kb"):
        ids = ctx.get(f"{kind}_ids", {})
        if rest not in ids:
            raise Unresolved(token)
        return ids[rest]
    if token in ctx:
        return ctx[token]
    raise Unresolved(token)


def render(value, ctx: dict):
    if isinstance(value, dict):
        return {render(k, ctx): render(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    if isinstance(value, str):
        whole = PLACEHOLDER.fullmatch(value)
        if whole:
            resolved = resolve(whole.group(1), ctx)
            return render(resolved, ctx) if isinstance(resolved, str) and "${" in resolved else resolved
        return PLACEHOLDER.sub(lambda m: str(resolve(m.group(1), ctx)), value)
    return value


# ----------------------------------------------------------------- procedures

def _tool_step(step: dict, extra_procs: dict) -> dict:
    step = dict(step)
    tool = step.pop("tool", None)
    if tool:
        step["tool_id"] = f"${{tool:{tool}}}"
        step["tool_name"] = tool
    on_failure = step.get("on_failure")
    if on_failure == "retry_then_escalate":
        retry_key = f"reintento_{tool}"
        if retry_key not in extra_procs:
            retry_step = {k: v for k, v in step.items() if k != "on_failure"}
            retry_step["on_failure"] = {"branches": [], "fallback": [
                {"type": "sub_procedure", "procedure_id": "${procedure:escalamiento_falla_tecnica}"}]}
            extra_procs[retry_key] = {
                "name": f"Reintento: {tool}",
                "type": "deterministic",
                "trigger": f"Only when another procedure hands off here because the {tool} tool just failed once. "
                           f"Never start it from a customer request.",
                "steps": [
                    {"type": "say", "message": "Tuve un problema para consultar eso. Dame un momento, lo intento de nuevo.",
                     "message_translations": {"en": {"value": "I had a problem checking that. Give me a moment, I'll try again."}}},
                    retry_step,
                ],
            }
        step["on_failure"] = {"branches": [], "fallback": [
            {"type": "sub_procedure", "procedure_id": f"${{procedure:{retry_key}}}"}]}
    elif isinstance(on_failure, dict):
        step["on_failure"] = {"branches": on_failure.get("branches", []),
                              "fallback": _expand(on_failure["fallback"], extra_procs)}
    return step


def _expand(steps: list, extra_procs: dict) -> list:
    out = []
    for step in steps:
        if step["type"] == "tool_call":
            out.append(_tool_step(step, extra_procs))
        elif step["type"] == "branch":
            branch = dict(step)
            branch["branches"] = [{**arm, "steps": _expand(arm["steps"], extra_procs)} for arm in step["branches"]]
            if "fallback" in step:
                branch["fallback"] = _expand(step["fallback"], extra_procs)
            out.append(branch)
        else:
            out.append(step)
    return out


def load_procedures() -> dict:
    procs, extra = {}, {}
    for path in sorted((ROOT / "procedure_configs").glob("*.json")):
        spec = read_json(path)
        if spec["type"] == "deterministic":
            spec = {**spec, "steps": _expand(spec["steps"], extra)}
        procs[path.stem] = spec
    procs.update(extra)
    return procs


def procedure_order(procs: dict) -> list[str]:
    deps = {k: set(re.findall(r"\$\{procedure:(\w+)\}", json.dumps(v))) for k, v in procs.items()}
    order, seen = [], set()

    def visit(key, stack=()):
        if key in seen:
            return
        if key in stack:
            raise SystemExit(f"procedure cycle: {' -> '.join(stack + (key,))}")
        for dep in sorted(deps[key]):
            if dep not in procs:
                raise SystemExit(f"procedure {key} references unknown procedure {dep}")
            visit(dep, stack + (key,))
        seen.add(key)
        order.append(key)

    for key in sorted(procs):
        visit(key)
    return order


def procedure_payload(spec: dict, ctx: dict) -> dict:
    payload = {"name": spec["name"], "type": spec["type"], "trigger": spec["trigger"]}
    if spec["type"] == "deterministic":
        payload["content"] = json.dumps({"steps": render(spec["steps"], ctx)}, ensure_ascii=False)
    else:
        payload["content"] = render(spec["content"], ctx)
    return payload


def check_structured(steps: list, path: str = "steps", context: str = "top", tools: dict | None = None) -> list[str]:
    """Documented validation rules for structured procedures, checked before publishing."""
    errors = []
    if not steps:
        errors.append(f"{path}: steps must not be empty")
    allowed = {
        "top": {"ask", "tell", "say", "tool_call", "branch", "sub_procedure", "system_tool"},
        "arm": {"ask", "tell", "say", "tool_call", "sub_procedure", "system_tool"},
        "on_failure": {"ask", "tell", "say", "sub_procedure", "system_tool", "retry"},
    }[context]
    for i, step in enumerate(steps):
        p, kind = f"{path}[{i}]", step.get("type")
        if kind not in allowed:
            errors.append(f"{p}: {kind} is not allowed in {context}")
        if kind in ("ask", "tell") and not step.get("instruction", "").strip():
            errors.append(f"{p}: {kind} needs an instruction")
        if kind == "say" and not step.get("message", "").strip():
            errors.append(f"{p}: say needs a message")
        if kind == "system_tool" and step.get("system_tool_name") == "end_call" and i != len(steps) - 1:
            errors.append(f"{p}: end_call must be the last step")
        if kind == "retry" and i != len(steps) - 1:
            errors.append(f"{p}: retry must be the last step in on_failure")
        if kind == "branch":
            if i > 0 and steps[i - 1].get("type") == "branch":
                errors.append(f"{p}: two If steps cannot be adjacent")
            types = {arm["condition"]["type"] for arm in step.get("branches", [])}
            if len(types) > 1:
                errors.append(f"{p}: all conditions in one If must share a type")
            if "expression" in types and i > 0 and steps[i - 1].get("type") == "ask":
                errors.append(f"{p}: expression If cannot directly follow an Ask")
            for j, arm in enumerate(step.get("branches", [])):
                errors += check_structured(arm.get("steps", []), f"{p}.branches[{j}]", "arm", tools)
            if step.get("fallback"):
                errors += check_structured(step["fallback"], f"{p}.fallback", "arm", tools)
        if kind == "tool_call":
            if not step.get("on_failure"):
                errors.append(f"{p}: tool_call without on_failure ends the call on failure")
            else:
                errors += check_structured(step["on_failure"].get("fallback", []), f"{p}.on_failure", "on_failure", tools)
            if tools is not None:
                tool = tools.get(step.get("tool_name"))
                if tool is None:
                    errors.append(f"{p}: unknown tool {step.get('tool_name')}")
                else:
                    props = tool["api_schema"]["request_body_schema"]["properties"]
                    for key in step.get("schema_overrides", {}):
                        field = key.removeprefix("request_body.")
                        if field not in props:
                            errors.append(f"{p}: schema_overrides key {key} is not a tool parameter")
                        elif "dynamic_variable" in props[field] or "constant_value" in props[field]:
                            errors.append(f"{p}: {key} is already fixed in the tool schema")
    return errors


# ---------------------------------------------------------------------- tests

def test_payload(spec: dict, ctx: dict, mocks: dict) -> dict:
    spec = copy.deepcopy(spec)
    mock_refs = spec.pop("mocks", None)
    payload = render(spec, ctx)
    if mock_refs:
        overrides = {}
        for tool, ref in mock_refs.items():
            mock = mocks[ref]
            if mock.get("error"):
                entry = {"parameter_conditions": [], "mock_result": mock["result"], "is_error": True}
            else:
                entry = {"parameter_conditions": [], "mock_result": json.dumps(render(mock, ctx), ensure_ascii=False)}
            overrides[ctx["tool_ids"][tool]] = [entry]
        payload["tool_mock_config"] = {
            "mocking_strategy": "selected", "fallback_strategy": "raise_error",
            "mocked_tool_ids": list(ctx["tool_ids"].values()),
        }
        payload["tool_mock_overrides"] = overrides
    return payload


# ---------------------------------------------------------------------- build

def tenant_context(tenant: str, state: dict, offline: bool) -> dict:
    cfg = read_json(ROOT / "agent_configs" / f"{tenant}.json")
    tstate = state.get("tenants", {}).get(tenant, {})
    tool_names = [p.stem for p in sorted((ROOT / "tool_configs").glob("*.json"))]
    procs = load_procedures()

    def ids(kind, keys):
        saved = tstate.get(kind, {})
        return {k: saved.get(k) or (f"offline_{kind}_{k}" if offline else None) for k in keys}

    ctx = {k: v for k, v in cfg.items()}
    ctx = {k: render(v, ctx) if isinstance(v, str) else v for k, v in ctx.items()}
    backend_url = ENV.get("BACKEND_URL") or ("https://cobranza-backend.example.com" if offline else None)
    if not backend_url:
        raise SystemExit("BACKEND_URL is required (public HTTPS URL of the FastAPI backend)")
    ctx.update({
        "session_var": SESSION_VAR,
        "backend_url": backend_url.rstrip("/"),
        "tenant_key_secret_id": tstate.get("secret_id") or ("offline_secret" if offline else None),
        "tool_ids": ids("tools", tool_names),
        "procedure_ids": ids("procedures", procs.keys()),
        "kb_ids": ids("kb", [p.stem for p in (ROOT / "knowledge_base").glob("*.md")]),
        "post_call_webhook_id": state.get("post_call_webhook_id"),
    })
    return ctx


def kb_documents(ctx: dict) -> dict:
    titles = {"faq": "Preguntas frecuentes", "ley_2300": "Ley 2300 de 2023", "tratamiento_datos": "Tratamiento de datos"}
    return {
        p.stem: {"name": f"{ctx['tenant_name']} · {titles.get(p.stem, p.stem)}",
                 "text": render(p.read_text(encoding="utf-8"), ctx)}
        for p in sorted((ROOT / "knowledge_base").glob("*.md"))
    }


def agent_payload(ctx: dict, state_tenant: dict) -> dict:
    template = read_json(ROOT / "agent_configs" / "_template.json")
    kb = [{"type": "text", "name": doc["name"], "id": ctx["kb_ids"][key], "usage_mode": "auto"}
          for key, doc in kb_documents(ctx).items()]
    tests = [{"test_id": tid} for tid in (state_tenant.get("tests") or {}).values() if tid]
    payload = render(template, {**ctx, "tool_ids": list(ctx["tool_ids"].values()), "knowledge_base": kb,
                                "attached_tests": tests})
    if not ctx.get("post_call_webhook_id"):
        payload["platform_settings"].pop("workspace_overrides")
    return payload


def build_tenant(tenant: str, state: dict, offline: bool) -> dict:
    ctx = tenant_context(tenant, state, offline)
    tstate = state.get("tenants", {}).get(tenant, {})
    tools = {p.stem: render(read_json(p), ctx) for p in sorted((ROOT / "tool_configs").glob("*.json"))}
    procs = load_procedures()
    mocks = read_json(ROOT / "test_configs" / "_mocks.json")
    tests = {p.stem: test_payload(read_json(p), ctx, mocks)
             for p in sorted((ROOT / "test_configs").glob("[0-9]*.json"))}
    return {
        "ctx": ctx,
        "tools": tools,
        "kb": kb_documents(ctx),
        "procedure_order": procedure_order(procs),
        "procedures": {k: procedure_payload(v, ctx) for k, v in procs.items()},
        "tests": tests,
        "agent": agent_payload(ctx, tstate),
    }


# ----------------------------------------------------------------- validation

def openapi() -> dict:
    cache = BUILD / "elevenlabs_openapi.json"
    if not cache.exists():
        BUILD.mkdir(exist_ok=True)
        spec = subprocess.run(["npx", "--no-install", "elevenlabs", "--spec"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout
        cache.write_text(spec, encoding="utf-8")
    spec = read_json(cache)
    schemas = spec["components"]["schemas"]

    def fix_refs(node):
        # The embedded spec has a few refs to "-Input" variants that only exist without the suffix.
        if isinstance(node, dict):
            ref = node.get("$ref", "")
            if ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[1]
                if name not in schemas:
                    base = re.sub(r"-(Input|Output)$", "", name)
                    node["$ref"] = f"#/components/schemas/{base}" if base in schemas else "#/$defs/any"
            for value in node.values():
                fix_refs(value)
        elif isinstance(node, list):
            for value in node:
                fix_refs(value)

    fix_refs(schemas)
    return spec


def validator_for(spec: dict, schema_name: str) -> Draft202012Validator:
    root = {"components": spec["components"], "$defs": {"any": {}}}
    registry = Registry().with_resource("urn:elevenlabs", Resource.from_contents(
        {**root, "$schema": "https://json-schema.org/draft/2020-12/schema"}))
    return Draft202012Validator({"$ref": f"urn:elevenlabs#/components/schemas/{schema_name}"}, registry=registry)


def validate_build(tenant: str, built: dict) -> list[str]:
    spec = openapi()
    errors = []

    def check(name, schema, payload):
        for err in validator_for(spec, schema).iter_errors(payload):
            errors.append(f"[{tenant}] {name}: {'/'.join(map(str, err.absolute_path))}: {err.message[:300]}")

    assigned = {a["dynamic_variable"] for tool in built["tools"].values() for a in tool.get("assignments", [])}
    for name, tool in built["tools"].items():
        check(f"tool {name}", "ToolRequestModel", {"tool_config": tool})
        # Placeholders only exist in dashboard tests; a live call has system__ vars and tool assignments.
        api_schema = tool.get("api_schema", {})
        for header, value in api_schema.get("request_headers", {}).items():
            if isinstance(value, dict) and not value.get("variable_name", "system__").startswith("system__"):
                errors.append(f"[{tenant}] tool {name}: header {header} reads a dynamic variable that live calls lack")
        body = json.dumps(api_schema.get("request_body_schema", {}))
        for var in re.findall(r'"dynamic_variable": "([^"]+)"', body):
            if not var.startswith("system__") and var not in assigned:
                errors.append(f"[{tenant}] tool {name}: {var} is never assigned by a tool")
    check("agent", "Body_Create_Agent_v1_convai_agents_create_post", built["agent"])
    for name, proc in built["procedures"].items():
        check(f"procedure {name}", "CreateProcedureRequestModel", proc)
        if proc["type"] == "deterministic":
            steps = json.loads(proc["content"])["steps"]
            errors += [f"[{tenant}] procedure {name}: {e}" for e in check_structured(steps, tools=built["tools"])]
            for arm_step in [s for s in steps if s["type"] == "branch"]:
                for arm in arm_step["branches"]:
                    if arm["condition"]["type"] == "expression":
                        check(f"procedure {name} expression", "ASTNode-Input", arm["condition"]["expression"])
    test_schema = {"llm": "CreateResponseUnitTestRequest", "tool": "CreateToolCallUnitTestRequest",
                   "simulation": "CreateSimulationTestRequest"}
    for name, test in built["tests"].items():
        check(f"test {name}", test_schema[test["type"]], test)

    prompt = built["agent"]["conversation_config"]["agent"]["prompt"]["prompt"]
    if len(prompt) / 4 > 2000:
        errors.append(f"[{tenant}] system prompt is ~{len(prompt) // 4} tokens; keep it under 2,000")
    # Rules the API enforces but the OpenAPI schema does not express.
    custom = built["agent"]["platform_settings"]["guardrails"].get("custom", {}).get("config", {}).get("configs", [])
    for guardrail in custom:
        label = f"[{tenant}] guardrail {guardrail['name']}"
        mode = guardrail.get("execution_mode", "streaming")
        if guardrail.get("evaluate_full_response_only"):
            errors.append(f"{label}: evaluate_full_response_only is not supported for voice agents")
        if guardrail.get("trigger_action", {}).get("type") == "retry" and mode != "blocking":
            errors.append(f"{label}: retry trigger action needs execution_mode blocking")
        if mode == "blocking":
            errors.append(f"{label}: blocking mode holds every reply; simulations time out and callers hear silence")
    leftover = [m for m in PLACEHOLDER.findall(json.dumps(built, ensure_ascii=False, default=str))
                if not m.startswith(("tool:", "procedure:", "kb:"))]
    if leftover:
        errors.append(f"[{tenant}] unresolved placeholders: {sorted(set(leftover))}")
    return errors


def cmd_build(args) -> int:
    state = load_state()
    BUILD.mkdir(exist_ok=True)
    all_errors = []
    for tenant in args.tenants:
        built = build_tenant(tenant, state, offline=True)
        out = BUILD / tenant
        out.mkdir(parents=True, exist_ok=True)
        for kind in ("tools", "procedures", "tests", "kb"):
            (out / kind).mkdir(exist_ok=True)
            for name, payload in built[kind].items():
                (out / kind / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        (out / "agent.json").write_text(json.dumps(built["agent"], ensure_ascii=False, indent=2))
        errors = validate_build(tenant, built)
        all_errors += errors
        prompt_tokens = len(built["agent"]["conversation_config"]["agent"]["prompt"]["prompt"]) // 4
        print(f"[{tenant}] {len(built['tools'])} tools, {len(built['procedures'])} procedures "
              f"({', '.join(built['procedure_order'])}), {len(built['tests'])} tests, "
              f"{len(built['kb'])} KB docs, prompt ~{prompt_tokens} tokens -> {out.relative_to(ROOT)}")
    for e in all_errors:
        print("ERROR", e)
    print("build OK: every payload matches the ElevenLabs OpenAPI schema and procedure rules"
          if not all_errors else f"{len(all_errors)} validation errors")
    return 1 if all_errors else 0


# ----------------------------------------------------------------------- push

def load_state() -> dict:
    return read_json(STATE_FILE) if STATE_FILE.exists() else {"tenants": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


class Api:
    def __init__(self):
        key = ENV.get("ELEVENLABS_API_KEY")
        if not key:
            raise SystemExit("ELEVENLABS_API_KEY is required")
        self.client = httpx.Client(base_url=ENV.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io"),
                                   headers={"xi-api-key": key}, timeout=60)

    def call(self, method: str, path: str, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if response.status_code >= 300:
            raise SystemExit(f"{method} {path} -> {response.status_code}\n{response.text[:3000]}")
        return response.json() if response.content else {}


def cmd_push(args) -> int:
    api, state = Api(), load_state()
    if not ENV.get("BACKEND_URL", "").startswith("https://"):
        raise SystemExit("BACKEND_URL must be the public https:// URL of the deployed backend")

    if args.webhook and not state.get("post_call_webhook_id"):
        created = api.call("POST", "/v1/workspace/webhooks", json={"settings": {
            "auth_type": "hmac", "name": "cobranza post-call",
            "webhook_url": f"{ENV['BACKEND_URL'].rstrip('/')}/webhooks/post-call"}})
        state["post_call_webhook_id"] = created["webhook_id"]
        save_state(state)
        print("\nPost-call webhook created. Set this in the backend environment (shown once):\n"
              f"  POST_CALL_WEBHOOK_SECRET={created.get('webhook_secret')}\n")

    for tenant in args.tenants:
        tstate = state.setdefault("tenants", {}).setdefault(tenant, {})
        cfg = read_json(ROOT / "agent_configs" / f"{tenant}.json")
        tenant_key = ENV.get(cfg["tenant_key_env"])
        if not tenant_key:
            raise SystemExit(f"{cfg['tenant_key_env']} is required")

        secret_name = f"cobranza_tenant_key_{tenant}"
        if tstate.get("secret_id"):
            api.call("PATCH", f"/v1/convai/secrets/{tstate['secret_id']}",
                     json={"type": "update", "name": secret_name, "value": tenant_key})
        else:
            tstate["secret_id"] = api.call("POST", "/v1/convai/secrets", json={
                "type": "new", "name": secret_name, "value": tenant_key})["secret_id"]
        save_state(state)

        # Tools and KB docs only need the secret id; the other ids do not exist yet.
        ctx = tenant_context(tenant, state, offline=True)

        tstate.setdefault("tools", {})
        for path in sorted((ROOT / "tool_configs").glob("*.json")):
            tool = render(read_json(path), ctx)
            if tstate["tools"].get(path.stem):
                api.call("PATCH", f"/v1/convai/tools/{tstate['tools'][path.stem]}", json={"tool_config": tool})
            else:
                tstate["tools"][path.stem] = api.call("POST", "/v1/convai/tools", json={"tool_config": tool})["id"]
            save_state(state)
        print(f"[{tenant}] tools: {len(tstate['tools'])}")

        tstate.setdefault("kb", {})
        tstate.setdefault("kb_hash", {})
        for key, doc in kb_documents(ctx).items():
            digest = hashlib.sha256(doc["text"].encode()).hexdigest()
            if tstate["kb"].get(key) and tstate["kb_hash"].get(key) == digest:
                continue
            tstate["kb"][key] = api.call("POST", "/v1/convai/knowledge-base/text", json=doc)["id"]
            tstate["kb_hash"][key] = digest
            save_state(state)
        print(f"[{tenant}] knowledge base: {len(tstate['kb'])} docs")

        built = build_tenant(tenant, state, offline=False)
        tstate.setdefault("tests", {})
        for key, payload in built["tests"].items():
            if tstate["tests"].get(key):
                api.call("PUT", f"/v1/convai/agent-testing/{tstate['tests'][key]}", json=payload)
            else:
                tstate["tests"][key] = api.call("POST", "/v1/convai/agent-testing/create", json=payload)["id"]
            save_state(state)
        print(f"[{tenant}] tests: {len(tstate['tests'])}")

        agent = agent_payload(tenant_context(tenant, state, offline=False), tstate)
        if tstate.get("agent_id"):
            api.call("PATCH", f"/v1/convai/agents/{tstate['agent_id']}", json=agent)
        else:
            tstate["agent_id"] = api.call("POST", "/v1/convai/agents/create", json=agent)["agent_id"]
        save_state(state)

        branches = api.call("GET", f"/v1/convai/agents/{tstate['agent_id']}/branches")["results"]
        main = next((b for b in branches if not b.get("parent_branch_id") and not b.get("is_archived")), branches[0])
        tstate["branch_id"] = main["id"]
        base = f"/v1/convai/agents/{tstate['agent_id']}/branches/{tstate['branch_id']}/procedures"

        tstate.setdefault("procedures", {})
        procs = load_procedures()
        for key in procedure_order(procs):
            payload = procedure_payload(procs[key], tenant_context(tenant, state, offline=False))
            if tstate["procedures"].get(key):
                api.call("PATCH", f"{base}/{tstate['procedures'][key]}/draft", json=payload)
            else:
                tstate["procedures"][key] = api.call("POST", base, json=payload)["procedure_id"]
            save_state(state)
        print(f"[{tenant}] procedures: {len(tstate['procedures'])}")

        api.call("PATCH", f"/v1/convai/agents/{tstate['agent_id']}", params={"branch_id": tstate["branch_id"]},
                 json={"version_description": args.message})
        print(f"[{tenant}] published {tstate['agent_id']}")
        register_agent(tenant, tstate["agent_id"])

    print_links(state)
    return 0


def register_agent(tenant: str, agent_id: str) -> None:
    sql = (f"insert into cobranza.tenant_agents (agent_id, tenant_id, label) values ('{agent_id}', '{tenant}', "
           f"'production') on conflict (agent_id) do nothing;")
    admin_url = ENV.get("DATABASE_ADMIN_URL")
    if not admin_url:
        print(f"[{tenant}] run this once in Supabase so post-call webhooks map to the tenant:\n  {sql}")
        return
    import asyncio

    import asyncpg

    async def run():
        conn = await asyncpg.connect(admin_url, statement_cache_size=0)
        try:
            await conn.execute(sql)
        finally:
            await conn.close()

    asyncio.run(run())
    print(f"[{tenant}] registered {agent_id} in cobranza.tenant_agents")


def print_links(state: dict) -> None:
    for tenant, t in state.get("tenants", {}).items():
        if t.get("agent_id"):
            print(f"[{tenant}] talk:      https://elevenlabs.io/app/talk-to?agent_id={t['agent_id']}")
            print(f"[{tenant}] dashboard: https://elevenlabs.io/app/agents/agents/{t['agent_id']}")


# ----------------------------------------------------------------------- test

def cmd_test(args) -> int:
    api, state = Api(), load_state()
    failed = 0
    for tenant in args.tenants:
        t = state.get("tenants", {}).get(tenant, {})
        if not t.get("agent_id"):
            raise SystemExit(f"[{tenant}] not pushed yet")
        body = {"tests": [{"test_id": tid} for tid in t["tests"].values()], "repeat_count": args.repeat}
        if args.llm:
            agent = api.call("GET", f"/v1/convai/agents/{t['agent_id']}")
            agent["conversation_config"]["agent"]["prompt"]["llm"] = args.llm
            body["agent_config_override"] = {"conversation_config": agent["conversation_config"],
                                             "platform_settings": agent["platform_settings"]}
        invocation = api.call("POST", f"/v1/convai/agents/{t['agent_id']}/run-tests", json=body)
        print(f"[{tenant}] running {len(body['tests'])} tests{' with ' + args.llm if args.llm else ''}...")
        while True:
            runs = invocation.get("test_runs", [])
            if runs and all(r["status"] != "pending" for r in runs):
                break
            time.sleep(5)
            invocation = api.call("GET", f"/v1/convai/test-invocations/{invocation['id']}")
        for run in sorted(runs, key=lambda r: r.get("test_name", "")):
            mark = "PASS" if run["status"] == "passed" else "FAIL"
            failed += run["status"] != "passed"
            rationale = ((run.get("condition_result") or {}).get("rationale") or {})
            print(f"  {mark}  {run.get('test_name')}")
            if run["status"] != "passed" and rationale:
                print(f"        {json.dumps(rationale, ensure_ascii=False)[:400]}")
    return 1 if failed else 0


def cmd_voices(args) -> int:
    api = Api()
    result = api.call("GET", "/v1/shared-voices", params={
        "language": "es", "accent": "colombian", "gender": "female", "page_size": 15})
    for voice in result.get("voices", []):
        print(f"{voice.get('voice_id')}  {voice.get('name')}  ({voice.get('accent')}, {voice.get('use_case')})")
    print("Set ELEVENLABS_VOICE_ID_AVANZA / ELEVENLABS_VOICE_ID_NEXO to the one you pick, then push again.")
    return 0


DEMO_TURNS = [
    "Hola, quiero ponerme al día con mi crédito.",
    "Los últimos cuatro de mi cédula son cuatro cuatro uno siete.",
    "Nací el catorce de mayo de mil novecientos noventa.",
    "Prefiero el plan en tres cuotas.",
    "Sí, confirmo ese plan.",
    "Sí, por favor envíame el link.",
    "No, eso es todo. Gracias.",
]


async def _chat(agent_id: str, turns: list[str], quiet_secs: float) -> str:
    import asyncio
    import websockets

    signed = Api().call("GET", "/v1/convai/conversation/get-signed-url", params={"agent_id": agent_id})["signed_url"]
    conversation_id = ""
    async with websockets.connect(signed, max_size=None) as ws:
        await ws.send(json.dumps({"type": "conversation_initiation_client_data",
                                  "conversation_config_override": {"conversation": {"text_only": True}}}))

        loop = asyncio.get_running_loop()

        async def drain() -> None:
            # Audio, VAD and ping events never stop, so only agent output extends the turn.
            nonlocal conversation_id
            deadline = loop.time() + quiet_secs
            while (remaining := deadline - loop.time()) > 0:
                try:
                    event = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
                except asyncio.TimeoutError:
                    return
                kind = event.get("type")
                if kind == "ping":
                    await ws.send(json.dumps({"type": "pong", "event_id": event["ping_event"]["event_id"]}))
                elif kind == "conversation_initiation_metadata":
                    conversation_id = event["conversation_initiation_metadata_event"]["conversation_id"]
                elif kind == "agent_response":
                    print(f"agent: {event['agent_response_event']['agent_response']}", flush=True)
                    deadline = loop.time() + quiet_secs
                elif kind == "agent_tool_response":
                    tool = event.get("agent_tool_response", {})
                    print(f"       [{tool.get('tool_name')}{' error' if tool.get('is_error') else ''}]", flush=True)
                    deadline = loop.time() + quiet_secs

        try:
            await drain()
            for text in turns:
                print(f"user:  {text}", flush=True)
                await ws.send(json.dumps({"type": "user_message", "text": text}))
                await drain()
        except websockets.ConnectionClosed as closed:
            print(f"(call ended: {closed.rcvd.reason if closed.rcvd else 'closed'})")
    return conversation_id


def cmd_chat(args) -> int:
    import asyncio

    state = load_state()
    tenant = args.tenants[0]
    agent_id = state.get("tenants", {}).get(tenant, {}).get("agent_id")
    if not agent_id:
        raise SystemExit(f"[{tenant}] not pushed yet")
    conversation_id = asyncio.run(_chat(agent_id, args.say or DEMO_TURNS, args.quiet))
    print(f"\nconversation_id: {conversation_id}")
    print(f"https://elevenlabs.io/app/agents/history/{conversation_id}")
    return 0


def cmd_status(args) -> int:
    state = load_state()
    print(json.dumps(state, indent=2) if state.get("tenants") else "nothing pushed yet")
    print_links(state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "push", "test", "chat", "voices", "status"):
        p = sub.add_parser(name)
        p.add_argument("--tenant", dest="tenants", action="append", choices=TENANTS)
        if name == "push":
            p.add_argument("--message", default="Deploy from agents-as-code")
            p.add_argument("--no-webhook", dest="webhook", action="store_false",
                           help="skip creating the workspace post-call webhook")
        if name == "test":
            p.add_argument("--llm", help="run the suite with another model, e.g. gpt-6-luna")
            p.add_argument("--repeat", type=int, default=1)
        if name == "chat":
            p.add_argument("--say", action="append", help="user turn; repeat for several (default: demo script)")
            p.add_argument("--quiet", type=float, default=8.0, help="seconds of silence that end an agent turn")
    args = parser.parse_args()
    args.tenants = args.tenants or TENANTS
    return {"build": cmd_build, "push": cmd_push, "test": cmd_test, "chat": cmd_chat,
            "voices": cmd_voices, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
