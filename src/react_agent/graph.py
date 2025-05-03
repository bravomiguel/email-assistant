"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
from langgraph.graph import StateGraph

from react_agent.configuration import Configuration
from react_agent.state import InputState, State
from react_agent.nodes import call_model, human_review_node, gmail_reply_node, tools
from react_agent.edges import route_model_output

# Define a new graph
builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node("call_model", call_model)
builder.add_node("tools", tools)
builder.add_node("human_review_node", human_review_node)

# Set the entrypoint as `call_model`
builder.add_edge("__start__", "call_model")

# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
    "call_model",
    route_model_output,
    ["tools", "human_review_node", "__end__"]
)

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")

# Compile the builder into an executable graph
graph = builder.compile(name="Email Assistant")
