from langchain_core.messages import AIMessage
from typing import Literal

from react_agent.state import State


# routing after model call
def route_model_output(state: State):
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.
    """
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # if there is no tool call, then we finish
    if not last_message.tool_calls:
        return "__end__"

    # if tool call is UpdateMemory, route to relevant memory update node based on memory type arg
    memory_type = last_message.tool_calls[0].get("args", {}).get("memory_type", None)
    if memory_type:
        return memory_type

    # if tool call is GMAIL_REPLY_TO_THREAD, route to human review node
    if last_message.tool_calls[-1].get("name", "") == "GMAIL_REPLY_TO_THREAD":
        return "human_review"

    # otherwise, route to tools node and execute relevant action
    return "tools"
