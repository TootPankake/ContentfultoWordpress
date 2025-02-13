from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
import asyncio
import random
from dotenv import load_dotenv
load_dotenv()
model = init_chat_model("gpt-4o-mini", model_provider="openai")

activities = ["walking", "knitting", "swimming", "barre", "hiking", "camping", "cycling", "painting", "croche"]

workflow = StateGraph(state_schema=MessagesState)
async def call_model(state: MessagesState):
    response = await model.ainvoke(state["messages"])
    return {"messages": response}

# Define the (single) node in the graph
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)
memory = MemorySaver()
application = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "0451"}}

# Variable to store the last notification message
last_notification = None
last_activity = None
rejection_count = 0
approval_count = 0

async def main():
    global last_notification, last_activity, rejection_count, approval_count

    while True:
        if last_notification and rejection_count == 0:
            query = f"Send a similar push notification as before: '{last_notification}'"
            print("Approval Streak: ", approval_count)
            if approval_count > 3:
                query = f"Try a brand new opposite tone from your last 4 notifications."
                approval_count = 0
        else:
            selected_activity = random.choice([act for act in activities if act != last_activity])
            last_activity = selected_activity  # Track last activity

            if rejection_count == 0:
                tone = "Keep it very short and purely factual with no emojis or fluff."
            elif rejection_count == 1:
                tone = "Make it simple and straightforward, removing most emojis."
            elif rejection_count == 2:
                tone = "Make it more direct and action-driven."
            else:
                tone = "Make it exciting and engaging."

            query = f"Generate a push notification for {selected_activity}. {tone}"

        input_messages = [SystemMessage(query)]
        output = await application.ainvoke({"messages": input_messages}, config)
        notification_message = output["messages"][-1].content
        last_notification = notification_message  # Store notification

        print("\nSystem:", query)
        print("AI:", notification_message)

        notification_pressed = input("Press notification? (y/n): ").strip().lower()

        if notification_pressed == "y":
            print("Notification pressed! Keeping the same tone.")
            rejection_count = 0  # Reset rejection count since it was accepted
            approval_count += 1
        else:
            print("Notification not pressed. Modifying tone and activity.")
            rejection_count += 1  # Increase rejection count to tone down next message
            print("Rejection Streak: ", rejection_count)
            approval_count = 0

asyncio.run(main())