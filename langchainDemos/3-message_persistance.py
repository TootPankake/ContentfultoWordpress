from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
import asyncio
from dotenv import load_dotenv
load_dotenv()

model = init_chat_model("gpt-4o-mini", model_provider="openai")

workflow = StateGraph(state_schema=MessagesState)
async def call_model(state: MessagesState):
    response = await model.ainvoke(state["messages"])
    return {"messages": response}

workflow.add_edge(START, "model")
workflow.add_node("model", call_model)
memory = MemorySaver()
application = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "0451"}}
alternate_config = {"configurable": {"thread_id": "0452"}}

async def main():
    query = "Hi! I'm Emre."
    input_messages = [HumanMessage(query)]
    output = await application.ainvoke({"messages": input_messages}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)


    query = "What's my name?"
    input_messages = [HumanMessage(query)]
    output = await application.ainvoke({"messages": input_messages}, config)
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)


    input_messages = [HumanMessage(query)] # still "What's my name"
    output = await application.ainvoke({"messages": input_messages}, alternate_config)     # change config thread for fresh convo
    print("\nUser: ", query)
    print("AI: ",output["messages"][-1].content)

asyncio.run(main())

