from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph, add_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import asyncio
from typing_extensions import Annotated, TypedDict
from typing import Sequence

from dotenv import load_dotenv
load_dotenv()
model = init_chat_model("gpt-4o-mini", model_provider="openai")

class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    language: str
    agent: str
    
pirate_prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "You talk like a pirate. Answer all questions to the best of your ability in {language}."),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

royalty_prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "You talk like a royalty. Answer all questions to the best of your ability in {language}."),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

# Define first agent function
async def call_pirate_agent(state: State):
    prompt = await pirate_prompt_template.ainvoke(state)
    response = await model.ainvoke(prompt)
    return {"messages": state["messages"] + [response]}

# Define second agent function
async def call_royalty_agent(state: State):
    prompt = await royalty_prompt_template.ainvoke(state)
    response = await model.ainvoke(prompt)
    return {"messages": state["messages"] + [response]}

# Function to decide which agent to use
def route_agent(state: State):
    if state["agent"] == "pirate":
        return "pirate_model"
    else:
        return "royalty_model"

# Add routing logic
workflow = StateGraph(state_schema=State)
workflow.add_conditional_edges(START, route_agent)
workflow.add_node("pirate_model", call_pirate_agent)
workflow.add_node("royalty_model", call_royalty_agent)

memory = MemorySaver()
application = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "0451"}}
alternate_config = {"configurable": {"thread_id": "0452"}}

async def main():
    query = "Hi! I'm Emre."
    language = "English"
    input_messages = [HumanMessage(query)]
    output = await application.ainvoke({"messages": input_messages, "language": language, "agent": "pirate"}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)


    query = "What's my name?"
    input_messages = [HumanMessage(query)]
    output = await application.ainvoke({"messages": input_messages, "language": language, "agent": "royalty"}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)


    # change config thread for fresh convo
    input_messages = [HumanMessage(query)] # still "What's my name"
    output = await application.ainvoke({"messages": input_messages, "language": language, "agent": "pirate"}, alternate_config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)

    language = "Spanish"
    query = "What's my name?"
    input_messages = [HumanMessage(query)] # still "What's my name"
    output = await application.ainvoke({"messages": input_messages, "language": language, "agent": "pirate"}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)
asyncio.run(main())

