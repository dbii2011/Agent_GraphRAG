import os
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_neo4j import Neo4jVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "ajdZoka3ALvP7WpgZoqcKkOSZ0irJeou")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "azerty00")

class AgentGraphRAG:
    def __init__(self):
        print("Initialisation des modèles Mistral...")
        self.llm = ChatMistralAI(model="mistral-small-latest", api_key="ajdZoka3ALvP7WpgZoqcKkOSZ0irJeou")
        self.embeddings = MistralAIEmbeddings(model="mistral-embed", api_key="ajdZoka3ALvP7WpgZoqcKkOSZ0irJeou")

        print("Connexion à Neo4j et vérification de l'index vectoriel...")
        
        print("Récupération des données et création manuelle de l'index...")

        # 1. On récupère les données via une requête simple
        
        # Exemple de requête pour récupérer tes noms de classes
        query = "MATCH (n:Classe) RETURN n.nom AS text, id(n) AS id"
        
        # Ici, on simule l'appel driver (Neo4j permet d'exécuter du cypher simplement)
        # Si tu n'as pas le driver importé, ajoute `from neo4j import GraphDatabase`
        # Pour simplifier, on va créer une liste de documents :
        documents = []
        # (Tu peux remplir cette liste avec tes données réelles si nécessaire)
        # Exemple : documents = [Document(page_content="Classe A"), Document(page_content="Classe B")]
        
        # 2. On crée le vecteur manuellement
        # Si tu as déjà créé l'index avec le Cypher, utilise from_existing_index :
        self.vector_store = Neo4jVector.from_existing_index(
            embedding=self.embeddings,
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
            index_name="classes_index"
        )
        
        # 3. Si l'index est vide, on ajoute les documents petit à petit (pour éviter le 400)
        # Envoie les données par petits paquets de 5 pour ne pas saturer Mistral
        # self.vector_store.add_documents(documents)

        retrieval_query = """
        OPTIONAL MATCH (node)-[:POSSEDE_ATTRIBUT]->(attr:Attribut)
        OPTIONAL MATCH (node)-[rel]->(autre)
        WHERE type(rel) <> 'POSSEDE_ATTRIBUT'
        RETURN "Classe: " + node.nom + 
               " | Description: " + coalesce(node.description, "Aucune") + 
               " | Attributs: [" + collect(DISTINCT attr.nom + " de type " + attr.type) + "]" +
               " | Relations: [" + collect(DISTINCT type(rel) + " vers " + coalesce(autre.nom, "")) + "]" AS text,
               score, 
               node {.*} AS metadata
        """

        vector_store_graphrag = Neo4jVector.from_existing_index(
            embedding=self.embeddings,
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
            index_name="classes_index",
            retrieval_query=retrieval_query
        )
        
        self.retriever = vector_store_graphrag.as_retriever(search_kwargs={"k": 3})

        prompt = ChatPromptTemplate.from_template(
            "Tu es un expert en architecture UML et ferroviaire. "
            "En te basant UNIQUEMENT sur le contexte extrait de la base de données ci-dessous, "
            "réponds à la question de l'utilisateur de manière claire.\n\n"
            "Contexte extrait du graphe :\n{context}\n\n"
            "Question : {input}\n\n"
            "Réponse :"
        )
        
        # --- LA NOUVELLE FAÇON DE FAIRE (LCEL) ---
        # Plus besoin de create_stuff_documents_chain !
        # On dit à LangChain : "Prends les documents, joins-les en texte, passe la question, applique le prompt, appelle le LLM, et sors du texte brut."
        
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        self.rag_chain = (
            {"context": self.retriever | format_docs, "input": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        print("Agent GraphRAG prêt !")

    def poser_question(self, question: str):
        # La chaîne prend désormais directement la question sous forme de texte simple
        return self.rag_chain.invoke(question)

# --- Interface Utilisateur ---
if __name__ == "__main__":
    agent = AgentGraphRAG()
    
    print("\n--- Assistant UML Ariane Coeur (Tapez 'stop' pour quitter) ---")
    while True:
        question_utilisateur = input("\nVotre question : ")
        
        if question_utilisateur.lower() in ["quitter", "exit", "stop", "q"]:
            print("Au revoir !")
            break
            
        if not question_utilisateur.strip():
            continue
            
        print("Recherche en cours dans le graphe...")
        try:
            resultat = agent.poser_question(question_utilisateur)
            print(f"\n🤖 Mistral : {resultat}")
        except Exception as e:
            print(f"\n❌ Erreur : {e}")