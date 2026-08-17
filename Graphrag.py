from langchain_graph_retriever import GraphRetriever
from langchain_core.vectorstores import Chroma
import os
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "TA_CLE_MISTRAL")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# 
vector_store = Chroma(embedding_function= MistralAIEmbeddings(model="mistral-embed", api_key=MISTRAL_API_KEY))

# Create the Graph Retriever
retriever = GraphRetriever(
    store=vector_store,
    # Define edges based on document metadata
    edges=[("keywords", "keywords")],
)

# Perform a retrieval
documents = retriever.retrieve("What is the capital of France?")

# Print the results
for doc in documents:
    print(doc.page_content)