import os
import re
from dotenv import load_dotenv

load_dotenv()

from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship, Path
from mistralai.client import Mistral


MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

MODEL = "mistral-small-latest"


class GraphAgent:
    def __init__(self):
        self.llm = Mistral(api_key=MISTRAL_API_KEY)
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def ask_mistral(self, prompt):
        response = self.llm.chat.complete(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()

    def get_schema_context(self):
        with self.driver.session() as session:
            labels = session.run("""
            MATCH (n)
            RETURN DISTINCT labels(n) AS labels
            """)

            relations = session.run("""
            MATCH ()-[r]->()
            RETURN DISTINCT type(r) AS relation, r.role AS role
            """)

            classes = session.run("""
            MATCH (c:Classe)
            RETURN c.nom AS classe
            ORDER BY c.nom
            LIMIT 100
            """)

            return {
                "labels": [record["labels"] for record in labels],
                "relations": [record["relation"] for record in relations],
                "classes": [record["classe"] for record in classes]
            }

    def clean_cypher(self, text):
        text = text.strip()
        text = re.sub(r"```cypher", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)
        return text.strip()

    def generate_cypher(self, question):
        schema = self.get_schema_context()

        prompt = f"""
Tu es un expert Neo4j/Cypher.

Tu dois générer une requête Cypher en lecture seule pour interroger un graphe de connaissances ARIANE.

Schéma réel du graphe :
{schema}

Modèle du graphe :
- (:Classe {{nom}})
- (:Attribut {{nom, key}})
- (:Type {{nom}})

Relations possibles :
- (:Classe)-[:HERITE_DE]->(:Classe)
- (:Classe)-[:A_ATTRIBUT]->(:Attribut)
- (:Attribut)-[:EST_DE_TYPE]->(:Type)
- (:Classe)-[:COMPOSE_DE]->(:Classe)
- (:Classe)-[:ASSOCIE_A]->(:Classe)
- (:Classe)-[:AGREGE]->(:Classe)
- (:Classe)-[:A_VALEUR]->(:Classe)

Règles :
- Retourne uniquement la requête Cypher.
- Pas de markdown.
- Pas d'explication.
- Ne jamais utiliser CREATE, MERGE, DELETE, SET, REMOVE, DROP, CALL.
- Utilise MATCH, OPTIONAL MATCH, WHERE, RETURN, ORDER BY, LIMIT.
- Pour les attributs d'une classe, utilise : (:Classe)-[:A_ATTRIBUT]->(:Attribut)
- Pour le type d'un attribut, utilise : (:Attribut)-[:EST_DE_TYPE]->(:Type)
- Pour l'héritage, utilise : [:HERITE_DE*]
- Le graphe est strictement orienté. Ne génère jamais de relations non orientées comme `-[*]-`.
- Pour un chemin entre deux classes, utilise la syntaxe Neo4j 5 : MATCH p = SHORTEST 2 (a)-[*]->(b) RETURN p. La flèche -> est OBLIGATOIRE.
- Recherche textuelle : Ne sois jamais sensible à la casse. Utilise "toLower(c.nom) = toLower('valeur')".

Question utilisateur :
{question}
"""

        cypher = self.ask_mistral(prompt)
        return self.clean_cypher(cypher)

    def validate_cypher(self, query):
        q = query.lower()

        forbidden = [
            "create ",
            "merge ",
            "delete ",
            "detach ",
            "set ",
            "remove ",
            "drop ",
            "call ",
            "load csv",
            "apoc"
        ]

        if not q.strip().startswith("match") and not q.strip().startswith("optional match"):
            raise ValueError("La requête générée n'est pas une requête de lecture.")

        for word in forbidden:
            if word in q:
                raise ValueError(f"Mot-clé interdit détecté : {word}")

    def serialize_value(self, value):
        """
        Transforme les objets Neo4j en dictionnaires lisibles par Mistral.
        """
        if isinstance(value, Node):
            return {
                "labels": list(value.labels),
                "properties": dict(value)
            }

        if isinstance(value, Relationship):
            return {
                "type": value.type,
                "properties": dict(value)
            }

        if isinstance(value, Path):
            return {
                "nodes": [
                    {
                        "labels": list(node.labels),
                        "properties": dict(node)
                    }
                    for node in value.nodes
                ],
                "relationships": [
                    {
                        "type": rel.type,
                        "properties": dict(rel)
                    }
                    for rel in value.relationships
                ]
            }

        if isinstance(value, list):
            return [self.serialize_value(v) for v in value]

        if isinstance(value, dict):
            return {k: self.serialize_value(v) for k, v in value.items()}

        return value

    def execute_cypher(self, query):

        self.validate_cypher(query)

        with self.driver.session() as session:
            result = session.run(query)
            rows = []

            for record in result:
                row = {}
                for key in record.keys():
                    row[key] = self.serialize_value(record[key])
                rows.append(row)

            return rows

    def answer_from_results(self, question, cypher, results):
        prompt = f"""
Tu es un assistant ARIANE.

Tu dois répondre en français à partir des résultats Neo4j.

Question utilisateur :
{question}

Requête exécutée :
{cypher}

Résultats récupérés depuis Neo4j :
{results}

Consignes :
- Ne dis pas seulement quelle requête a été faite.
- Donne directement l'information trouvée.
- Si le résultat est vide, dis que le graphe actuel ne contient pas l'information.
- Si le résultat contient un chemin, explique le chemin étape par étape.
- Réponds clairement et simplement.
"""

        return self.ask_mistral(prompt)

    def ask(self, question):
        cypher = self.generate_cypher(question)
        print("\n--- Requête Cypher générée ---")
        print(cypher)

        results = self.execute_cypher(cypher)
        print("\n--- Données récupérées depuis Neo4j ---")
        print(results)

        answer = self.answer_from_results(question, cypher, results)
        return answer


if __name__ == "__main__":
    agent = GraphAgent()

    print("Agent Neo4j + Mistral prêt.")
    print("Tape exit pour quitter.")

    while True:
        question = input("\nQuestion > ")

        if question.lower() in ["exit", "quit", "q"]:
            break

        try:
            response = agent.ask(question)
            print("\n--- Réponse finale ---")
            print(response)
        except Exception as e:
            print("\nErreur :", e)

    agent.close()