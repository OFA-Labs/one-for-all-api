"""Deliberately small deterministic grammar; this is not AI interpretation."""
from urllib.parse import urlsplit

from .contracts import Command, ExecutionError, Plan, Step, Target


class DeterministicPlanner:
    def __init__(self, config):
        self.config = config

    def plan(self, command: Command, capabilities: dict) -> Plan:
        text = command.text.strip()
        if text.lower().startswith("open "):
            name = text[5:].strip().strip('"')
            self.config.app(name)
            return Plan(title=text, steps=[Step(operation="app.open", target=Target(app=name))], source="deterministic")
        if text.lower().startswith("browse "):
            url = text[7:].strip()
            p = urlsplit(url)
            return Plan(title=text, steps=[Step(operation="browser.open", url=url)],
                        allowed_origins=[f"{p.scheme}://{p.netloc.lower()}"], source="deterministic")
        if text.lower().startswith("read file "):
            return Plan(title=text, steps=[Step(operation="file.read", target=Target(path=text[10:].strip('"')))],
                        source="deterministic")
        raise ExecutionError("UNSUPPORTED_COMMAND", "Supported typed commands: open <allowed app>, browse <allowed URL>, read file <allowed path>. Use a structured plan for other operations.")


class MockPlannerAdapter:
    """Fixture lookup for integration tests; never advertised as live reasoning."""
    def __init__(self, fixtures: dict[str, Plan]):
        self.fixtures = fixtures

    def plan(self, command: Command, capabilities: dict) -> Plan:
        if command.text not in self.fixtures:
            raise ExecutionError("UNSUPPORTED_COMMAND", "No deterministic plan fixture matches this command.")
        return self.fixtures[command.text].model_copy(update={"source": "mock_planner"}, deep=True)
