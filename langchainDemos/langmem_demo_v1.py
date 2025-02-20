import time
from langgraph.store.memory import InMemoryStore
from langmem import create_manage_memory_tool, create_search_memory_tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv
load_dotenv()

from langmem import create_manage_memory_tool, create_search_memory_tool
from langgraph.config import get_store, InMemoryStore, InMemorySaver
from langchain_openai import OpenAIEmbeddings
from langchain.agents import create_react_agent
from langchain.memory import ConversationBufferMemory

# Step 1: Initialize Memory Store
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": "openai:text-embedding-3-small"
    }
)

# Define a namespace for memory storage
namespace = ("agent_memories",)

# Step 2: Create Memory Tools for Adding and Searching Memories
memory_tools = [
    create_manage_memory_tool(namespace),  # Tool for managing memories
    create_search_memory_tool(namespace)   # Tool for searching memories
]

# Step 3: Set up Memory Saver (Checkpointing)
checkpointer = InMemorySaver()

# Step 4: Define the Prompt Function
def prompt(state):
    """
    Retrieves relevant memories from storage and appends them to the system prompt.
    """
    store = get_store()  # Access the memory store
    items = store.search(namespace, query=state["messages"][-1].content)  # Search for relevant memories

    # Format retrieved memories
    memories = "\n\n".join(str(item) for item in items) if items else "No relevant memories found."
    
    system_msg = {"role": "system", "content": f"## Memories:\n\n{memories}"}
    return [system_msg] + state["messages"]

# Step 5: Create the Agent with Memory-Enabled Features
agent = create_react_agent(
    llm="gpt-4o-mini",  # Using Claude as the agent model
    prompt=prompt,
    tools=memory_tools,
    store=store,
    checkpointer=checkpointer
)

# Step 6: Example Function to Run the Agent
def chat_with_agent(user_input):
    """
    Sends user input to the agent and retrieves a response.
    """
    state = {"messages": [{"role": "user", "content": user_input}]}
    response = agent(state)  # Run agent with the provided input
    return response

# Example Usage

print("Chatbot with memory is ready! Type your messages below.\n")
while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("Exiting chat.")
        break
    response = chat_with_agent(user_input)
    print("Agent:", response)