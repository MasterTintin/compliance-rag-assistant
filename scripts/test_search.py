from src.retrieval.embedder import LocalSentenceTransformerEmbedder
from src.retrieval.vector_store import QdrantVectorStore


def interactive_search():
    print("==================================================")
    print("Compliance RAG Assistant - Interactive Search")
    print("==================================================")
    print("Initializing Search Engine & Loading Model...")

    embedder = LocalSentenceTransformerEmbedder(model_name="BAAI/bge-m3")
    vector_store = QdrantVectorStore(host="localhost", port=6333, collection_name="compliance_docs")

    print("\n✅ System Ready! Type 'exit' or 'q' to quit.\n")

    while True:
        query_text = input("\n พิมพ์คำถามของคุณ: ").strip()

        if not query_text:
            continue

        if query_text.lower() in ["exit", "q", "quit"]:
            print(" See you later!")
            break

        print(f"🔍 Searching for: '{query_text}'...")

        query_vector = embedder.embed_text(query_text)

        results = vector_store.search_similar(query_vector=query_vector, top_k=3)

        print("\n Found Relevant Contexts:")
        print("=" * 60)
        for idx, res in enumerate(results, start=1):
            payload = res["payload"]
            score = res["score"]
            print(f"[{idx}] Score: {score:.4f} | Page: {payload.get('page_number')} | Section: {payload.get('section_title')}")
            print(f"    Text: {payload.get('text')[:200]}...\n")
            print("-" * 60)


if __name__ == "__main__":
    interactive_search()