# Retrieval Augmented Generation, might not be entirely relevant to our implementation

import os
import getpass
import bs4
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import MessagesState, StateGraph
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
load_dotenv()

# Step 1: Initialize the Chat Model
llm = init_chat_model("gpt-4o-mini", model_provider="openai")

# Step 2: Initialize the Embeddings Model
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

# Step 3: Create an In-Memory Vector Store
vector_store = InMemoryVectorStore(embeddings)

# Step 4: Load Documents from Web
loader = WebBaseLoader(
    web_paths=("https://lilianweng.github.io/posts/2023-06-23-agent/",),
    bs_kwargs=dict(
        parse_only=bs4.SoupStrainer(
            class_=("post-content", "post-title", "post-header")
        )
    ),
)
docs = loader.load()

# Step 5: Split Documents into Chunks
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
all_splits = text_splitter.split_documents(docs)

# Step 6: Index Chunks into the Vector Store
_ = vector_store.add_documents(documents=all_splits)

# Step 7: Define a Retrieval Tool
@tool(response_format="content_and_artifact")
def retrieve(query: str):
    """Retrieve information related to a query."""
    retrieved_docs = vector_store.similarity_search(query, k=2)
    serialized = "\n\n".join(
        (f"Source: {doc.metadata}\n" f"Content: {doc.page_content}")
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs

# Step 8: Initialize the State Graph for Message Management
graph_builder = StateGraph(MessagesState)

# Step 9: Define the Query or Respond Function
def query_or_respond(state: MessagesState):
    """Generate tool call for retrieval or respond."""
    llm_with_tools = llm.bind_tools([retrieve])
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

# Step 10: Define the Tool Node for Retrieval
tools = ToolNode([retrieve])

# Step 11: Test the Retrieval-Augmented Chatbot
query = "What are the key takeaways from the document?"
response = retrieve.invoke(query)
print("\n🔹 Query:", query)
print("\n🔹 Response:\n", response)


