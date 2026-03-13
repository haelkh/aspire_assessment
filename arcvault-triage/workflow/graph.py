"""
LangGraph workflow definition for the ArcVault Triage system.

This module defines the workflow graph that orchestrates
the message triage pipeline.
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from workflow.state import TriageState
from workflow.nodes import (
    classify_node,
    enrich_node,
    route_node,
    output_node,
    escalate_node
)


def should_escalate(state: TriageState) -> Literal["escalate", "output"]:
    """
    Determine if the message should be escalated.

    Args:
        state: Current workflow state.

    Returns:
        "escalate" if escalation is needed, "output" otherwise.
    """
    if state.get("escalation_flag", False):
        return "escalate"
    return "output"


def build_workflow() -> StateGraph:
    """
    Build the LangGraph workflow for message triage.

    The workflow follows this structure:
    1. classify_node - Analyze and categorize the message
    2. enrich_node - Extract entities and create summary
    3. route_node - Determine queue and escalation status
    4. output_node/escalate_node - Write results to output

    Returns:
        Compiled LangGraph workflow.
    """
    # Create the graph with our state schema
    graph = StateGraph(TriageState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("enrich", enrich_node)
    graph.add_node("route", route_node)
    graph.add_node("output", output_node)
    graph.add_node("escalate", escalate_node)

    # Set entry point
    graph.set_entry_point("classify")

    # Add linear edges for the main flow
    graph.add_edge("classify", "enrich")
    graph.add_edge("enrich", "route")

    # Add conditional edge for escalation routing
    graph.add_conditional_edges(
        "route",
        should_escalate,
        {
            "escalate": "escalate",
            "output": "output"
        }
    )

    # Both paths end the workflow
    graph.add_edge("output", END)
    graph.add_edge("escalate", END)

    return graph.compile()


def process_message(message: str, source: str) -> dict:
    """
    Process a single message through the triage workflow.

    This is a convenience function that builds and runs the workflow
    for a single message.

    Args:
        message: The customer message to process.
        source: The source of the message (Email, Web Form, Support Portal).

    Returns:
        Dictionary containing all processed fields.
    """
    workflow = get_workflow()

    # Initialize state with input
    initial_state = {
        "message": message,
        "source": source
    }

    # Run the workflow
    result = workflow.invoke(initial_state)

    return result


# Module-level workflow instance (compiled once)
_workflow = None


def get_workflow():
    """
    Get or create the compiled workflow instance.

    Returns:
        Compiled LangGraph workflow.
    """
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow
