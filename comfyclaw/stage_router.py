"""
StageRouter — Progressive tool disclosure based on pipeline stage.

When enabled, the router filters the agent's tool list so that only tools
relevant to the current pipeline stage are visible.  This reduces
hallucinated tool calls and improves workflow construction correctness.

Stages proceed in order::

    planning → construction → conditioning → enhancement → finalization

The agent may also jump backwards (e.g. from enhancement back to
construction to fix a wiring issue).
"""

from __future__ import annotations

STAGES = ("planning", "construction", "conditioning", "enhancement", "finalization")

STAGE_TOOLS: dict[str, set[str]] = {
    "planning": {
        "inspect_workflow",
        "report_evolution_strategy",
        "read_skill",
        "query_available_models",
        "explore_nodes",
        "transition_stage",
    },
    "construction": {
        "add_node",
        "connect_nodes",
        "delete_node",
        "set_param",
        "inspect_workflow",
        "query_available_models",
        "read_skill",
        "transition_stage",
    },
    "conditioning": {
        "set_prompt",
        "add_regional_attention",
        "add_controlnet",
        "set_param",
        "inspect_workflow",
        "read_skill",
        "transition_stage",
    },
    "enhancement": {
        "add_lora_loader",
        "add_hires_fix",
        "add_inpaint_pass",
        "set_param",
        "add_node",
        "connect_nodes",
        "delete_node",
        "inspect_workflow",
        "query_available_models",
        "read_skill",
        "transition_stage",
    },
    "finalization": {
        "validate_workflow",
        "finalize_workflow",
        "inspect_workflow",
        "set_param",
        "delete_node",
        "connect_nodes",
        "transition_stage",
    },
}


class StageRouter:
    """Filter tools based on the current pipeline stage.

    Parameters
    ----------
    enabled :
        When ``False`` (default), all tools are always available — the router
        is a transparent pass-through.  Set to ``True`` to activate stage gating.
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.current_stage: str = STAGES[0]

    def reset(self) -> None:
        """Reset to the planning stage."""
        self.current_stage = STAGES[0]

    def transition_to(self, stage: str) -> None:
        """Move to *stage*.

        Raises ``ValueError`` if the stage name is unrecognised.
        """
        if stage not in STAGE_TOOLS:
            raise ValueError(
                f"Unknown stage {stage!r}. Valid stages: {', '.join(STAGES)}"
            )
        self.current_stage = stage

    def get_current_tool_names(self) -> list[str]:
        """Return sorted list of tool names available in the current stage."""
        return sorted(STAGE_TOOLS.get(self.current_stage, set()))

    def filter_tools(self, all_tools: list[dict]) -> list[dict]:
        """Return the subset of *all_tools* allowed in the current stage.

        When the router is disabled, returns *all_tools* unchanged.
        """
        if not self.enabled:
            return all_tools

        allowed = STAGE_TOOLS.get(self.current_stage, set())
        return [t for t in all_tools if t["function"]["name"] in allowed]
