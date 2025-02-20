from langchain_openai import ChatOpenAI
from langgraph.func import entrypoint
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langmem import create_manage_memory_tool, create_search_memory_tool
from dotenv import load_dotenv
load_dotenv()

# Set up store and checkpointer
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": "openai:text-embedding-3-small",
    }
)
my_llm = ChatOpenAI(model="gpt-4o-mini")


def prompt(state):
    """Prepare messages with context from existing memories."""
    memories = store.search(
        ("memories",),
        query=state["messages"][-1].content,
    )
    system_msg = f"""You are a memory manager. Extract and manage all important knowledge, rules, and events using the provided tools.



Existing memories:
<memories>
{memories}
</memories>

Use the manage_memory tool to update and contextualize existing memories, create new ones, or delete old ones that are no longer valid.
You can also expand your search of existing memories to augment using the search tool."""
    return [{"role": "system", "content": system_msg}, *state["messages"]]


# Create the memory extraction agent
manager = create_react_agent(
    "gpt-4o-mini",
    prompt=prompt,
    tools=[
        # Agent can create/update/delete memories
        create_manage_memory_tool(namespace=("memories",)),
        create_search_memory_tool(namespace=("memories",)),
    ],
)


# Run extraction in background
@entrypoint(store=store)  # (1)
def app(messages: list):
    response = my_llm.invoke(
        [
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            *messages,
        ]
    )

    # Extract and store triples (Uses store from @entrypoint context)
    manager.invoke({"messages": messages})
    return response


app.invoke(
    [
        {
            "role": "user",
            "content": "Alice manages the cheeseburger team and mentors Bob, who is also on the team.",
        }
    ]
)


app.invoke(
    [
        {
            "role": "user",
            "content": "Bob used to have a crush on Alice, but he broke his knee.",
        }
    ]
)

print(store.search(("memories",)))
