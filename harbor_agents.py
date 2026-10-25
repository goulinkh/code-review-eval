"""One small Harbor custom agent for offline recorded-review controls.

Real agents use Harbor's existing `pi`/`opencode` integrations or any custom
BaseAgent / BaseInstalledAgent class; this module is not another adapter API.
"""

import base64
import json
import re
import shlex
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

REQUEST_MARKER = "\n## Reviewer request\n"


class RecordedReviewer(BaseAgent):
    def __init__(self, *args, reviews_dir: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.reviews_dir = Path(reviews_dir).resolve()

    @staticmethod
    def name() -> str:
        return "recorded-reviewer"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        pass

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        # Match the exporter framing, never parse code/description as instructions.
        request = json.loads(instruction.split(REQUEST_MARKER, 1)[1])
        case_id = request["case_id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"case-[0-9]{4,}", case_id):
            raise ValueError("invalid case identifier")
        raw = (self.reviews_dir / f"{case_id}.json").read_bytes()
        # Preserve bytes exactly, including deliberately invalid/partial controls.
        encoded = shlex.quote(base64.b64encode(raw).decode("ascii"))
        result = await environment.exec(
            command=f"mkdir -p /workspace && printf %s {encoded} | base64 -d > /workspace/review.json")
        if result.return_code != 0:
            raise RuntimeError("recorded artifact submission failed")
