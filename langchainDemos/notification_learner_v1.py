from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
import asyncio
import random
from dotenv import load_dotenv
load_dotenv()
model = init_chat_model("gpt-4o-mini", model_provider="openai")

# This version has a list of activities AND a a list of favorites that the notifications track
activities = ["walking", "knitting", "swimming", "barre", "hiking", "camping", "cycling", "painting", "croche"]
favs = ['knitting', 'croche']


workflow = StateGraph(state_schema=MessagesState)
async def call_model(state: MessagesState):
    response = await model.ainvoke(state["messages"])
    return {"messages": response}

workflow.add_edge(START, "model")
workflow.add_node("model", call_model)
memory = MemorySaver()
application = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "0451"}}

async def generate_notification(activity, tone):
    """Generate a push notification with a specific activity and tone."""
    query = f"Generate a push notification to entice the user about {activity}. Keep the tone {tone}."
    input_messages = [SystemMessage(query)]
    output = await application.ainvoke({"messages": input_messages}, config)
    return output["messages"][-1].content

async def main():
    tone = "engaging and fun"  # Initial tone
    used_activities = set()

    while True:
        # Pick an activity that hasn't been used yet
        available_activities = [act for act in activities if act not in used_activities]
        if not available_activities:
            print("\nNo more activities left to suggest! Exiting...")
            break

        activity = random.choice(available_activities)
        used_activities.add(activity)

        # Generate notification
        print(tone)
        print(favs)
        notification = await generate_notification(activity, tone)
        print(f"\nSystem: {notification}")

        # Ask user if they pressed it
        notification_pressed = input("Press notification (y/n, q to quit): ").strip().lower()
        
        if notification_pressed == "y":
            # Add to favorites and keep tone unchanged
            if activity not in favs:
                favs.append(activity)
            print(f"\n✅ {activity} added to favorites!\n")
        
        elif notification_pressed == "n":
            # Change tone and pick a new activity
            tone = random.choice(["more persuasive", "curious", "exciting", "mysterious", "casual"])
            print("\n🔄 Trying a different approach...\n")
            continue

        elif notification_pressed == "q":
            print("\nExiting...")
            break

        else:
            print("\nInvalid input. Please enter 'y', 'n', or 'q'.")
            continue
    

asyncio.run(main())

