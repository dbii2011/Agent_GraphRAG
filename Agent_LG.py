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

    @staticmethod
    def _retirer_sources_visibles(reponse: str) -> str:
        """Masque les références techniques sans modifier les faits de la réponse."""
        reponse = re.sub(r"\s*\[Source\s*:[^\]]+\]", "", reponse, flags=re.IGNORECASE)
        reponse = re.sub(
            r"\n\s*#{1,6}\s*\*{0,2}Sources(?:\s+finales[^\n]*)?\*{0,2}\s*.*$",
            "",
            reponse,
            flags=re.IGNORECASE | re.DOTALL,
        )
        reponse = re.sub(
            r"\n\s*Sources\s*:\s*(?:\n\s*-\s*[^\n]+)*\s*$",
            "",
            reponse,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\n{3,}", "\n\n", reponse).strip()

    @staticmethod
    def _formater_chemin_metier(chemin: dict) -> str:
        """Formate sans LLM le chemin validé retourné par Neo4j."""
        noms = {
            concept.get("id"): concept.get("nom") or concept.get("id", "")
            for concept in chemin.get("concepts", [])
        }

        def nom(identifiant):
            return noms.get(identifiant, str(identifiant or "").replace("_", " ").capitalize())

        if not chemin.get("trouve"):
            detectes = chemin.get("concepts_detectes", [])
            if len(detectes) < 2 and not (chemin.get("depart") and chemin.get("arrivee")):
                return (
                    "Je n’ai pas pu identifier deux concepts métier distincts dans la question. "
                    "Précise le concept de départ et celui d’arrivée."
                )
            return (
                f"Aucun chemin métier validé n’a été trouvé entre **{nom(chemin.get('depart'))}** "
                f"et **{nom(chemin.get('arrivee'))}** dans la limite de cinq relations."
            )

        relations = chemin.get("relations", [])
        lignes = [
            f"- **{nom(relation.get('source'))}** — `{relation.get('type', 'RELATION')}` → "
            f"**{nom(relation.get('cible'))}**"
            for relation in relations
        ]
        nombre = len(relations)
        introduction = (
            f"Le chemin métier validé entre **{nom(chemin.get('depart'))}** et "
            f"**{nom(chemin.get('arrivee'))}** comporte {nombre} "
            f"relation{'s' if nombre != 1 else ''} :"
        )
        return introduction + "\n\n" + "\n".join(lignes)

    @staticmethod
    def _schema_depuis_retrieval(resultat: dict) -> dict | None:
        """Construit le petit graphe à afficher, sans demander sa structure au LLM."""
        chemin = resultat.get("chemin_metier", {})
        source = chemin if chemin.get("trouve") else resultat.get("graphe_metier", {})
        relations = source.get("relations", [])
        concepts = source.get("concepts", [])
        if not relations:
            return None
        ids_utiles = {
            identifiant
            for relation in relations
            for identifiant in (relation.get("source"), relation.get("cible"))
        }
        noms = {
            concept.get("id"): concept.get("nom") or concept.get("id")
            for concept in concepts
            if concept.get("id") in ids_utiles
        }
        ordre_ids = [
            concept.get("id") for concept in concepts
            if concept.get("id") in ids_utiles
        ]
        ordre_ids.extend(sorted(ids_utiles - set(ordre_ids)))
        return {
            "nodes": [
                {"id": identifiant, "label": noms.get(identifiant, identifiant.replace("_", " ").capitalize())}
                for identifiant in ordre_ids
            ],
            "links": [
                {
                    "source": relation.get("source"),
                    "target": relation.get("cible"),
                    "label": relation.get("type", "RELATION"),
                }
                for relation in relations
            ],
        }

    @staticmethod
    def _retour(texte: str, schema: dict | None, inclure_graphe: bool):
        return {"reponse": texte, "graphe": schema} if inclure_graphe else texte

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
        inclure_graphe: bool = False,
    ):
        debut = time.time()
        logger.info("Question reçue : %s", question)

        try:
            resultat_retrieval = self.retriever.retrieve(
                question,
                historique=historique,
            )
            schema_reponse = self._schema_depuis_retrieval(resultat_retrieval)
            if resultat_retrieval.get("mode") == "CHEMIN_METIER":
                chemin = resultat_retrieval.get("chemin_metier", {})
                reponse_controlee = self._formater_chemin_metier(chemin)
                if not chemin.get("trouve"):
                    return self._retour(reponse_controlee, None, inclure_graphe)
                resultat = self.llm.invoke([
                    {
                        "role": "system",
                        "content": (
                            "Tu reformules un chemin Neo4j validé en français naturel. "
                            "Transforme chaque relation en une phrase grammaticalement correcte, "
                            "puis explique brièvement la connexion indirecte. Respecte exactement "
                            "le sens source, relation, cible. N'ajoute, ne supprime et ne déduis "
                            "aucune relation. N'affiche ni code, ni nom technique en majuscules, "
                            "ni source, ni tableau. Réponds directement et en un court paragraphe."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question : {question}\n\n"
                            f"Chemin contrôlé à reformuler :\n{reponse_controlee}"
                        ),
                    },
                ])
                texte = self._retirer_sources_visibles(resultat.content)
                return self._retour(texte, schema_reponse, inclure_graphe)
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
                        "métamodèle des extraits documentaires. "
                        "Réponds d'abord directement à la question dès la première phrase. "
                        "Adapte strictement le contenu à la demande : ne transforme pas une "
                        "question ciblée en rapport général. N'ajoute ni définition, ni attributs, "
                        "ni procédure, ni exemple si ces éléments ne sont pas demandés. "
                        "Utilise au maximum trois sections courtes. N'utilise aucun tableau Markdown : "
                        "présente les résultats sous forme de phrases ou de listes à puces courtes. "
                        "Ne répète pas la même information dans une synthèse. "
                        "Les relations de graphe_metier sont des connaissances issues des fiches, "
                        "pas des associations UML. Respecte leur champ condition et cite leurs preuves. "
                        "Une sélection pilote ne décrit pas tous les équipements ni tous les types existants. "
                        "Si la question demande un sous-graphe métier, restitue uniquement les concepts et "
                        "relations présents dans graphe_metier. N'ajoute jamais de relation 'possible', "
                        "supposée ou reconstruite depuis un passage. Si graphe_metier.relations est vide, "
                        "indique explicitement qu'aucune relation métier validée n'a été retrouvée. "
                        "Pour le mode CHEMIN_METIER, utilise exclusivement chemin_metier. Présente chaque "
                        "étape dans l'ordre, en respectant le sens source/type/cible enregistré. Si trouve "
                        "vaut false, indique qu'aucun chemin validé n'a été trouvé ou que deux concepts "
                        "n'ont pas pu être identifiés ; n'invente jamais une connexion. "
                        "Les sources servent uniquement à contrôler ton raisonnement en interne. "
                        "N'affiche aucune citation, aucun nom de fichier, aucun numéro de passage "
                        "et aucune section 'Sources' dans la réponse. Ignore les chunks non utilisés. "
                        "N'invente aucune classe, relation, cardinalité ou procédure. Si le contexte ne suffit "
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
        texte = self._retirer_sources_visibles(resultat.content)
        return self._retour(texte, schema_reponse, inclure_graphe)


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
