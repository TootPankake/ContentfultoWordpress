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
    language: str # language passed in as class variable
    
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You talk like a pirate. Answer all questions to the best of your ability in {language}.",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

workflow = StateGraph(state_schema=State)
async def call_model(state: State):
    prompt = await prompt_template.ainvoke(state)
    response = await model.ainvoke(prompt)
    return {"messages": response}

workflow.add_edge(START, "model")
workflow.add_node("model", call_model)
memory = MemorySaver()
application = workflow.compile(checkpointer=memory)

# Different conversation threads with their own id's
config = {"configurable": {"thread_id": "0451"}}
alternate_config = {"configurable": {"thread_id": "0452"}} 

async def main():
    query = "Hi! I'm Emre."
    language = "English"
    input_messages = [HumanMessage(query)]
    output = await application.ainvoke({"messages": input_messages, "language": language}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)


    query = "What's my name?"
    input_messages = [HumanMessage(query)]
    output = await application.ainvoke({"messages": input_messages, "language": language}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)


    # change config thread for fresh convo
    input_messages = [HumanMessage(query)] # still "What's my name"
    output = await application.ainvoke({"messages": input_messages, "language": language}, alternate_config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)

    language = "Spanish"
    query = "What's my name?"
    input_messages = [HumanMessage(query)]
    output = await application.ainvoke({"messages": input_messages, "language": language}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)
asyncio.run(main())

