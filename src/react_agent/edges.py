from langchain_core.messages import AIMessage
from typing import Literal

from react_agent.state import State


# routing after model call
def route_model_output(state: State):
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("tools" or "human_review_node" or "memory_manager").
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # If there is no tool call, then we finish
    if not last_message.tool_calls:
        return "memory_manager"

    # Otherwise we execute the requested actions
    if last_message.tool_calls[-1].get("name", "") == "GMAIL_REPLY_TO_THREAD":
        return "human_review_node"

    return "tools"