"""Small native Codex app-server client for isolated, read-only fixture runs."""

import json
import os
import queue
import re
import subprocess
import threading
import time


def answer_text(items):
    """Keep format checks on the final answer without hiding progress claims."""
    if any(item.get("phase") not in ("commentary", "final_answer") for item in items):
        raise ValueError("Unknown assistant message phase")
    finals = [item["text"] for item in items if item["phase"] == "final_answer"]
    if len(finals) != 1 or not finals[0].strip():
        raise ValueError("Expected exactly one nonempty final answer")
    return finals[0], "\n\n".join(item["text"] for item in items)


class Client:
    def __init__(self, package, workspace, with_plugin, trace, *, rootly_read_tools=None, fixture_server=None,
                 bundled_read_tools=None):
        if bundled_read_tools is not None:
            allowed = json.loads((package / "adapters/read-tools.json").read_text())["tools"]
            if (not with_plugin or rootly_read_tools is not None or fixture_server is not None
                    or not bundled_read_tools or not set(bundled_read_tools) <= set(allowed)):
                raise ValueError("Bundled live checks require only allowlisted reads and no standalone/fixture server")
            declared = json.loads((package / ".mcp.json").read_text())
            if declared != {"mcpServers": {"rootly": {"type": "http", "url": "https://mcp.rootly.com/mcp?toolsets=all&readonly=true"}}}:
                raise ValueError("Unexpected bundled server declaration")
            # With a portable root manifest, Codex discovers mcp.json rather
            # than the compatibility overlay. Check both, never just the alias.
            portable = json.loads((package / "mcp.json").read_text())
            if portable != {"$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                            "mcpServers": {"rootly": {"type": "streamable-http", "url": "https://mcp.rootly.com/mcp?toolsets=all&readonly=true"}}}:
                raise ValueError("Unexpected portable server declaration")
        self.trace = trace
        self.events = queue.Queue()
        self.sequence = 0
        command = ["codex", "app-server", "--stdio"]
        settings = [
            "features.apps=false", "features.hooks=false", "features.skill_mcp_dependency_install=false",
            # These ephemeral probes measure one skill invocation, not delegation.
            # A spawned thread can require rollout persistence unavailable here.
            "features.multi_agent=false", "agents.enabled=false",
            "web_search=\"disabled\"", "plugins._default.enabled=false",
            'plugins.rootly@rootly-agent-skills.enabled=' + str(with_plugin).lower(),
            # Plugin server settings need the full plugin id; the short key is silently ignored.
            # Pass it unquoted: a quoted segment in a -c dotted path is also ignored.
            'plugins.rootly@rootly-agent-skills.mcp_servers.rootly.enabled=' + str(bundled_read_tools is not None).lower(),
            'marketplaces.rootly-agent-skills.source_type="local"',
            "marketplaces.rootly-agent-skills.source=" + json.dumps(str(package)),
        ]
        # Disable every existing standalone MCP connection without emitting its
        # config (which could include credentials) or starting its server.
        existing = json.loads(subprocess.check_output(["codex", "mcp", "list", "--json"],
                                                     cwd=workspace, text=True))
        for server in existing:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", server["name"]):
                raise ValueError("Cannot safely encode an existing server name in CLI config")
            settings.append(f'mcp_servers.{server["name"]}.enabled=false')
            # Some listed servers come from account/managed sources rather than
            # config.toml. A bare enabled=false table fails transport validation.
            # Supply a nonfunctional transport without copying any credentials.
            if server["transport"]["type"] == "stdio":
                settings.append(f'mcp_servers.{server["name"]}.command="/usr/bin/false"')
            else:
                settings.append(f'mcp_servers.{server["name"]}.url="http://127.0.0.1:9"')
        # Opt-in for separately authorized live checks. Fixture callers
        # never supply this argument and retain no live MCP connections.
        if bundled_read_tools is not None:
            settings.extend([
                'plugins.rootly@rootly-agent-skills.mcp_servers.rootly.enabled_tools=' + json.dumps(bundled_read_tools),
                'plugins.rootly@rootly-agent-skills.mcp_servers.rootly.default_tools_approval_mode="approve"',
            ])
        if rootly_read_tools is not None:
            if fixture_server is not None:
                raise ValueError("Live and fixture servers cannot be combined")
            if not rootly_read_tools:
                raise ValueError("Live checks require a nonempty tool allowlist")
            settings.extend([
                'mcp_servers.rootly.enabled=true',
                'mcp_servers.rootly.url="https://mcp.rootly.com/mcp?toolsets=all&readonly=true"',
                'mcp_servers.rootly.enabled_tools=' + json.dumps(rootly_read_tools),
                'mcp_servers.rootly.default_tools_approval_mode="approve"',
            ])
        if fixture_server is not None:
            settings.extend([
                'mcp_servers.rootly_fixture.enabled=true',
                'mcp_servers.rootly_fixture.command=' + json.dumps(fixture_server["command"]),
                'mcp_servers.rootly_fixture.args=' + json.dumps(fixture_server["args"]),
                'mcp_servers.rootly_fixture.enabled_tools=' + json.dumps(fixture_server["tools"]),
                'mcp_servers.rootly_fixture.default_tools_approval_mode="approve"',
            ])
        for setting in settings:
            command.extend(["-c", setting])
        self.stderr = open(trace.name + ".stderr", "x")
        self.process = subprocess.Popen(command, cwd=workspace, text=True, bufsize=1,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.request("initialize", {"clientInfo": {"name": "rootly-fixture-tests", "version": "1.0"},
                                        "capabilities": {"experimentalApi": True}})
        except Exception:
            self.close()
            raise
        self.send({"jsonrpc": "2.0", "method": "initialized"})

    def _read(self):
        for line in self.process.stdout:
            try:
                self.events.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        self.events.put(None)

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def receive(self, timeout):
        value = self.events.get(timeout=timeout)
        if value is None:
            raise RuntimeError("Codex app-server exited unexpectedly")
        self.trace.write(json.dumps(value) + "\n")
        self.trace.flush()
        if "method" in value and "id" in value:
            self.send({"jsonrpc": "2.0", "id": value["id"], "error": {
                "code": -32601, "message": "Interactive grants are disabled in this test harness"}})
        return value

    def request(self, method, params, timeout=45):
        if method == "thread/start" and "model" not in params:
            model = os.environ.get("ROOTLY_EVAL_CODEX_MODEL")
            if model:
                params = {**params, "model": model}
        self.sequence += 1
        request_id = self.sequence
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.receive(max(0.01, deadline - time.monotonic()))
            if value.get("id") == request_id and "method" not in value:
                if "error" in value:
                    raise RuntimeError(value["error"])
                return value["result"]
        raise TimeoutError(method)

    def receive_turn(self, thread_id, turn_id, timeout):
        """Keep unrelated/child completion out of a single-agent probe result."""
        if not thread_id or not turn_id:
            raise ValueError("Expected explicit thread and turn identifiers")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            event = self.receive(max(.01, deadline - time.monotonic()))
            params = event.get("params", {})
            if params.get("item", {}).get("type") == "subAgentActivity":
                raise RuntimeError("Unexpected delegation in single-agent probe; inspect retained trace")
            if params.get("threadId") != thread_id:
                continue
            event_turn = params.get("turnId") or params.get("turn", {}).get("id")
            if event_turn == turn_id:
                return event
        raise TimeoutError("Expected model turn event")

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.stderr.close()

