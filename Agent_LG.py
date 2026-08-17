import os
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_core.tools import tool
from langchain.agents import create_agent
from neo4j import GraphDatabase
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
import  re
import logging
import functools
import time

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
MODEL = "mistral-small-latest"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AgentLG")

def chronometrer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        debut = time.time()
        logger.info(f"→ Appel de {func.__name__}({args}, {kwargs})")
        resultat = func(*args, **kwargs)
        logger.info(f"← {func.__name__} terminé en {time.time() - debut:.2f}s")
        return resultat
    return wrapper


class AgentLG:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.llm = ChatMistralAI(model=MODEL,api_key=MISTRAL_API_KEY, timeout= 30)
        self.embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=MISTRAL_API_KEY)
        agent_self = self  

        @tool
        @chronometrer
        def rechercher_classes(terme: str) -> str:
            """Recherche les classes dont le titre contient ce terme."""
            with agent_self.driver.session() as session:
                resultat = session.run(
                    "MATCH (c:Classe) WHERE toLower(c.nom) CONTAINS toLower($terme) "
                    "RETURN c.nom AS nom LIMIT 15",
                    terme=terme,
                )
                noms = [r["nom"] for r in resultat]
            if not noms:
                return f"Aucune classe trouvée contenant '{terme}'."
            return "Classes trouvées : " + ", ".join(noms)
        
        @tool
        @chronometrer
        def rechercher_documents(terme: str) -> str:
            """Recherche les documents dont le titre contient ce terme."""
            with agent_self.driver.session() as session:
                resultat = session.run(
            "MATCH (d:Document) WHERE toLower(d.titre) CONTAINS toLower($terme) "
            "RETURN d.id AS id, d.titre AS titre LIMIT 15",
            terme=terme,
        )
                docs = [f"{r['id']} ({r['titre']})" for r in resultat]
                if not docs:
                   return f"Aucun document trouvé contenant '{terme}'."
                return "Documents trouvés : " + ", ".join(docs)

        @tool
        @chronometrer
        def get_schema_context() -> str:
            """Donne une vision globale en lecture seule du schéma du graphe."""
            return agent_self.get_schema_context()

        @tool
        @chronometrer
        def interroger_graphe_ariane(cypher: str) -> str:
            """verifier la requete cypher et l'executer"""
            return agent_self._valider_et_executer(cypher)
        
        @tool
        @chronometrer
        def rechercher_documentation(question: str, classes_pertinentes: list[str] = None, documents_pertinents: list[str] = None) -> str:
            """Recherche par similarité vectorielle des passages pertinents pour répondre à la question.
            Si la question concerne une classe, fournis 'classes_pertinentes'. 
            Si la question concerne un document spécifique, fournis 'documents_pertinents'."""
            
            if not classes_pertinentes and not documents_pertinents:
                return "Erreur : Veuillez fournir au moins une classe ou un document pertinent."

            vecteur = agent_self.embeddings.embed_query(question)
            SEUIL_PERTINENCE = 0.65  
            
            with agent_self.driver.session() as session:
                if classes_pertinentes:
                    # Cas 1 : Exploite tous les documents liés à ces classes
                    requete = """
                    UNWIND $classes AS nom_classe
                    MATCH (c:Classe {nom: nom_classe})<-[:DECRIT]-(d:Document)<-[:APPARTIENT_A]-(chunk:Chunk)
                    WITH DISTINCT chunk, c.nom AS source, d.id AS document,
                         vector.similarity.cosine(chunk.embedding, $vec) AS score
                    WHERE score >= $seuil
                    RETURN chunk.texte AS texte, source, document, score
                    ORDER BY score DESC LIMIT 5
                    """
                    parametres = {"classes": classes_pertinentes, "vec": vecteur, "seuil": SEUIL_PERTINENCE}
                else:
                    # Cas 2 : Accède directement aux documents ciblés
                    requete = """UNWIND $documents AS doc_id
                    MATCH (d:Document {id: doc_id})<-[:APPARTIENT_A]-(chunk:Chunk)
                    OPTIONAL MATCH (d)-[:DECRIT]->(c:Classe)
                    WITH DISTINCT chunk, coalesce(c.nom, d.id) AS source, d.id AS document,
                    vector.similarity.cosine(chunk.embedding, $vec) AS score
                    WHERE score >= $seuil
                    RETURN chunk.texte AS texte, source, document, score
                    ORDER BY score DESC LIMIT 5 """
                    parametres = {"documents": documents_pertinents, "vec": vecteur, "seuil": SEUIL_PERTINENCE}
                    
                resultats = session.run(requete, **parametres)
                
                extraits = []
                for r in resultats:
                    extraits.append(f"[Source: {r['source']} | Score: {r['score']:.2f}]\n{r['texte']}")
                    
                if not extraits:
                    return f"Aucun extrait assez pertinent trouvé pour répondre à cette question (seuil {SEUIL_PERTINENCE})."
                
                return "\n\n---\n\n".join(extraits)
                
            
        @tool
        @chronometrer
        def etendre_au_voisinage(noms_classes: list[str]) -> list[str]:
            """Étend une liste de classes à leurs classes voisines directes (héritage, composition,
            association, agrégation). À utiliser après rechercher_classes et avant
            rechercher_documentation pour construire un périmètre de recherche complet."""
            with agent_self.driver.session() as session:
                resultat = session.run(
            """
            UNWIND $noms AS nom
            MATCH (c:Classe {nom: nom})
            OPTIONAL MATCH (c)-[:HERITE_DE|COMPOSE_DE|ASSOCIE_A|AGREGE]-(voisin:Classe)
            RETURN collect(DISTINCT c.nom) + collect(DISTINCT voisin.nom) AS perimetre
            """,
            noms=noms_classes,)
                return list(set(resultat.single()["perimetre"]))     

        self.tools = [
            rechercher_classes,
            rechercher_documents,
            get_schema_context,
            interroger_graphe_ariane,
            rechercher_documentation,
            etendre_au_voisinage,
        ]
        system_prompt = f"""Tu es un expert Neo4j/Cypher et un assistant métier.
 
Schéma réel du graphe :
avec l'outil get_schema_context()
 
Modèle du graphe :
- (:Classe {{nom}})
- (:Attribut {{nom, key}})
- (:Type {{nom}})
- (:Document {{id, titre}})
- (:Chunk {{id, texte, position, embedding}})
 
MÉTHODOLOGIE OBLIGATOIRE POUR RÉPONDRE :
1. Analyse la question.
2. Identifie si elle concerne une Classe (utilise `rechercher_classes`) ou un Document (utilise `rechercher_documents`).
3. Utilise get_schema_context pour avoir une idée sur tous les noeuds qui existent et les différentes relations entre eux 
3. Si la question est purement structurelle (attributs, héritage, cardinalités) -> get_schema_context pour construire la requete cypher puis interroger_graphe_ariane seul.Si elle est métier/procédurale/documentaire → rechercher_documentation.
4. Ne demande jamais la permission à l'utilisateur, enchaîne tes outils pour trouver la réponse finale.
5. Quand on te demande le chemin entre 2 entité tu peux essayer le sens inverse aussi
 
Relations possibles :
- (:Classe)-[:HERITE_DE]->(:Classe)
- (:Classe)-[:A_ATTRIBUT]->(:Attribut)
- (:Attribut)-[:EST_DE_TYPE]->(:Type)
- (:Classe)-[:COMPOSE_DE]->(:Classe)
- (:Classe)-[:ASSOCIE_A]->(:Classe)
- (:Classe)-[:AGREGE]->(:Classe)
- (:Classe)-[:A_VALEUR]->(:Classe)
- (:Chunk)-[:APPARTIENT_A]->(Document)
- (:Document)-[:DECRIT]->(:Classe)
 
Règles :
- Ne jamais utiliser CREATE, MERGE, DELETE, SET, REMOVE, DROP, CALL.
- Utilise MATCH, OPTIONAL MATCH, WHERE, RETURN, ORDER BY, LIMIT.
- Pour les attributs d'une classe, utilise : (:Classe)-[:A_ATTRIBUT]->(:Attribut)
- Pour le type d'un attribut, utilise : (:Attribut)-[:EST_DE_TYPE]->(:Type)
- Pour l'héritage, utilise : [:HERITE_DE*]
- Le graphe est strictement orienté. Ne génère jamais de relations non orientées comme -[*]-.
- Pour un chemin entre deux classes, utilise la syntaxe Neo4j 5 :
  MATCH p = SHORTEST 2 (a)-[*]->(b) RETURN p.
- Recherche textuelle : Ne sois jamais sensible à la casse. Utilise toLower(c.nom) = toLower('valeur').
- Si tu n'es pas certain du nom exact d'une classe, utilise rechercher_classes AVANT
  de générer une requête Cypher.
- Retourne une réponse finale claire en français, jamais de Cypher brut dans ta réponse.
- pour les questions structurelles , utilise uniquement le schema des relations et shortestpath
- les types d'une classe dans le modele ariane veut dire les classe qui en herite
"""

        self.executor = create_agent(model=self.llm, tools=self.tools, system_prompt=system_prompt)


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
                "MATCH (a:Attribut) RETURN DISTINCT a.nom AS attribut ORDER BY attribut LIMIT 1000"
            )
            types = session.run(
                "MATCH (t:Type) RETURN DISTINCT t.nom AS type ORDER BY type LIMIT 500"
            )
            documents = session.run(
                "MATCH (d:Document) RETURN DISTINCT d.titre AS document ORDER BY document LIMIT 500"
            )
            data = {
                "labels": sorted({label for record in labels for label in record["labels"]}),
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
        requete = requete_cypher.replace("```cypher", "").replace("```", "").strip()
        mots_interdits = [
            "CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP", "DETACH",
            "CALL", "LOAD", "FOREACH", "GRANT", "DENY", "REVOKE", "ALTER",
        ]
        if not re.match(r"^(MATCH|OPTIONAL\s+MATCH|UNWIND)\b", requete, re.IGNORECASE):
            return "Erreur de sécurité : la requête doit commencer par MATCH, OPTIONAL MATCH ou UNWIND."
        if any(re.search(rf"\b{mot}\b", requete.upper()) for mot in mots_interdits):
            return "Erreur de sécurité : seule la lecture est autorisée."
        try:
            with self.driver.session() as session:
                donnees = [record.data() for record in session.run(requete)]
                if not donnees:
                    return "La base de données n'a renvoyé aucun résultat pour cette question."
                return str(donnees)
        except Exception as e:
            return f"Erreur technique Neo4j : {str(e)}"

    def ask(self, question: str, historique: list[dict[str, str]] | None = None) -> str:
        debut = time.time()
        logger.info(f"Question reçue : {question}")
    
        try:
            messages = list(historique or [])[-12:]
            messages.append({"role": "user", "content": question})
            resultat = self.executor.invoke(
            {"messages": messages},
            config={"recursion_limit": 15},
        )
        except Exception as e:
            logger.error(f"Erreur lors de l'appel agent : {e}")
            return "Le service est temporairement surchargé (limite de capacité atteinte). Réessaie dans quelques instants."
    
        logger.info(f"Temps total : {time.time() - debut:.2f}s")
        for i, m in enumerate(resultat["messages"]):
           role = type(m).__name__
           if hasattr(m, "tool_calls") and m.tool_calls:
               logger.info(f"  [{i}] {role} → outils appelés : {[t['name'] for t in m.tool_calls]}")
           elif hasattr(m, "content") and m.content:
               apercu = str(m.content)[:100]
               logger.info(f"  [{i}] {role} : {apercu}")
    
        return resultat["messages"][-1].content


def main():
    agent = AgentLG()
    print("- Bienvenue dans l'assistant Ariane Cœur :)")
    while True:
        question_utilisateur = input("\nVotre question : ")
        if question_utilisateur.lower() in ["quitter", "exit", "stop"]:
            print("Au revoir.")
            break

        print("Recherche en cours...")
        reponse_finale = agent.ask(question_utilisateur)
        print(f"\nRéponse : {reponse_finale}")


if __name__ == "__main__":
    main()
