from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from config import OPENAI_API_TOKEN
import os

# Set API key for OpenAI
os.environ["OPENAI_API_KEY"] = OPENAI_API_TOKEN

class State(TypedDict):
    messages: Annotated[list, add_messages]

# Initialize OpenAI's chat model with GPT-4-turbo
llm = ChatOpenAI(model="gpt-4o", temperature=0.7, streaming=True)

# Define the chatbot function
def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

# Build the state graph
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")

# Compile the graph
graph = graph_builder.compile()

# Define a test state with input messages
test_state = {
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "How many seasons does Eureka have?"}
    ]
}

# Test using the compiled graph's stream method
for output_state in graph.stream(test_state):
    ai_message = output_state['chatbot']['messages'][0]
    print(ai_message.content)