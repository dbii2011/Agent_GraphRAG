import logging
import os
import re
import time

import httpx
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from neo4j import GraphDatabase

from graphrag_retriever import GraphRAGRetriever


load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AgentLG")


class AgentLG:
    """Assistant Arianes fondé sur un pipeline GraphRAG contrôlé."""

    def __init__(self):
        if not MISTRAL_API_KEY:
            raise ValueError("MISTRAL_API_KEY est absent du fichier .env.")
        if not NEO4J_PASSWORD:
            raise ValueError("NEO4J_PASSWORD est absent du fichier .env.")

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )
        self.llm = ChatMistralAI(
            model=MODEL,
            api_key=MISTRAL_API_KEY,
            timeout=30,
            temperature=0,
        )
        self.embeddings = MistralAIEmbeddings(
            model="mistral-embed",
            api_key=MISTRAL_API_KEY,
        )
        self.retriever = GraphRAGRetriever(self.driver, self.embeddings)

    def close(self):
        self.driver.close()

    def get_schema_context(self) -> str:
        """Retourne un aperçu borné du schéma réellement présent dans Neo4j."""
        with self.driver.session() as session:
            labels = session.run("MATCH (n) RETURN DISTINCT labels(n) AS labels")
            relations = session.run(
                "MATCH ()-[r]->() RETURN DISTINCT type(r) AS relation ORDER BY relation"
            )
            classes = session.run(
                "MATCH (c:Classe) RETURN c.nom AS classe ORDER BY c.nom LIMIT 1000"
            )
            attributs = session.run(
                "MATCH (a:Attribut) RETURN DISTINCT a.nom AS attribut "
                "ORDER BY attribut LIMIT 1000"
            )
            types = session.run(
                "MATCH (t:Type) RETURN DISTINCT t.nom AS type ORDER BY type LIMIT 500"
            )
            documents = session.run(
                "MATCH (d:Document) RETURN DISTINCT d.titre AS document "
                "ORDER BY document LIMIT 500"
            )
            data = {
                "labels": sorted(
                    {label for record in labels for label in record["labels"]}
                ),
                "relations": [record["relation"] for record in relations],
                "classes": [record["classe"] for record in classes],
                "attributs": [record["attribut"] for record in attributs],
                "types": [record["type"] for record in types],
                "documents": [record["document"] for record in documents],
            }
        return (
            f"Labels : {', '.join(data['labels'])}\n"
            f"Relations : {', '.join(data['relations'])}\n"
            f"Classes ({len(data['classes'])}) : {', '.join(data['classes'])}\n"
            f"Attributs ({len(data['attributs'])}) : {', '.join(data['attributs'])}\n"
            f"Types : {', '.join(data['types'])}\n"
            f"Documents ({len(data['documents'])}) : {', '.join(data['documents'])}"
        )

    def _valider_et_executer(self, requete_cypher: str) -> str:
        """Exécute une requête Cypher après validation stricte en lecture seule."""
        requete = (
            requete_cypher.replace("```cypher", "").replace("```", "").strip()
        )
        mots_interdits = [
            "CREATE",
            "MERGE",
            "SET",
            "DELETE",
            "REMOVE",
            "DROP",
            "DETACH",
            "CALL",
            "LOAD",
            "FOREACH",
            "GRANT",
            "DENY",
            "REVOKE",
            "ALTER",
        ]
        if not re.match(
            r"^(MATCH|OPTIONAL\s+MATCH|UNWIND)\b", requete, re.IGNORECASE
        ):
            return (
                "Erreur de sécurité : la requête doit commencer par MATCH, "
                "OPTIONAL MATCH ou UNWIND."
            )
        if any(re.search(rf"\b{mot}\b", requete.upper()) for mot in mots_interdits):
            return "Erreur de sécurité : seule la lecture est autorisée."
        try:
            with self.driver.session() as session:
                donnees = [record.data() for record in session.run(requete)]
                if not donnees:
                    return (
                        "La base de données n'a renvoyé aucun résultat "
                        "pour cette question."
                    )
                return str(donnees)
        except Exception as exc:
            return f"Erreur technique Neo4j : {exc}"

    def ask(
        self,
        question: str,
        historique: list[dict[str, str]] | None = None,
    ) -> str:
        debut = time.time()
        logger.info("Question reçue : %s", question)

        try:
            resultat_retrieval = self.retriever.retrieve(
                question,
                historique=historique,
            )
            logger.info(
                "Retrieval GraphRAG : mode=%s racines=%s classes=%s chunks=%s",
                resultat_retrieval["mode"],
                resultat_retrieval["classes_racines"],
                len(resultat_retrieval["sous_graphe"]["classes"]),
                len(resultat_retrieval["chunks"]),
            )
            contexte = self.retriever.contexte_pour_llm(resultat_retrieval)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Tu es l'assistant métier Arianes. Réponds uniquement à partir "
                        "du contexte GraphRAG fourni. Distingue clairement les faits du "
                        "métamodèle des extraits documentaires. N'invente aucune classe, "
                        "relation, cardinalité ou procédure. Si le contexte ne suffit "
                        "pas, dis précisément quelle information manque. Pour une "
                        "question structurelle, privilégie les classes, attributs et "
                        "relations. Pour une question métier, cite les passages sous la "
                        "forme [Source : fichier — passage N]. Réponds en français, de "
                        "manière claire et concise."
                    ),
                },
                *(list(historique or [])[-8:]),
                {
                    "role": "user",
                    "content": (
                        f"Question actuelle : {question}\n\n"
                        f"Contexte GraphRAG contrôlé :\n{contexte}"
                    ),
                },
            ]
            resultat = self.llm.invoke(messages)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.error("Connexion au service Mistral impossible : %s", exc)
            return (
                "Le graphe Neo4j est disponible, mais le service Mistral est "
                "actuellement inaccessible. Vérifie la connexion réseau ou le proxy."
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Erreur HTTP Mistral (%s) : %s",
                exc.response.status_code,
                exc,
            )
            if exc.response.status_code == 429:
                return (
                    "Le service Mistral est temporairement surchargé. "
                    "Réessaie dans quelques instants."
                )
            return (
                "Le service Mistral a refusé la requête. "
                "Vérifie la clé API et la configuration."
            )
        except Exception:
            logger.exception("Erreur inattendue lors de l'appel agent")
            return (
                "Une erreur inattendue empêche l'agent de répondre. "
                "Consulte les journaux du serveur."
            )

        logger.info("Temps total : %.2fs", time.time() - debut)
        reponse = resultat.content
        citations = resultat_retrieval.get("citations", [])
        if citations and "Sources :" not in reponse:
            reponse += "\n\nSources :\n" + "\n".join(
                f"- {citation}" for citation in citations
            )
        return reponse


def main():
    agent = AgentLG()
    try:
        print("- Bienvenue dans l'assistant Arianes")
        while True:
            question = input("\nVotre question : ")
            if question.lower() in {"quitter", "exit", "stop"}:
                print("Au revoir.")
                break
            print("Recherche en cours...")
            print(f"\nRéponse : {agent.ask(question)}")
    finally:
        agent.close()


if __name__ == "__main__":
    main()
