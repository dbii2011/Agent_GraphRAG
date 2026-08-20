import json
import re
import time
import unicodedata
from difflib import SequenceMatcher


RELATIONS_STRUCTURELLES = ["HERITE_DE", "COMPOSE_DE", "ASSOCIE_A", "AGREGE"]
MOTS_AMBIGUS = {
    "a", "au", "aux", "ce", "ces", "dans", "de", "des", "du", "en", "est",
    "et", "la", "le", "les", "ou", "par", "pour", "que", "qui", "son", "sur",
    "un", "une",
}


def normaliser(texte: str) -> str:
    texte = re.sub(r"(?<=[A-ZÀ-Ý])(?=[A-ZÀ-Ý][a-zà-ÿ])", " ", texte or "")
    texte = re.sub(r"(?<=[a-zà-ÿ0-9])(?=[A-ZÀ-Ý])", " ", texte or "")
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", texte))


def tokens(texte: str) -> set[str]:
    return {t for t in normaliser(texte).split() if len(t) >= 2}


class GraphRAGRetriever:
    """Construit un contexte GraphRAG déterministe et entièrement sourcé."""

    def __init__(self, driver, embeddings, cache_seconds: int = 300):
        self.driver = driver
        self.embeddings = embeddings
        self.cache_seconds = cache_seconds
        self._catalogue = []
        self._catalogue_charge_a = 0.0

    def _charger_catalogue(self) -> list[dict]:
        if self._catalogue and time.time() - self._catalogue_charge_a < self.cache_seconds:
            return self._catalogue
        with self.driver.session() as session:
            records = session.run(
                """
                MATCH (c:Classe)
                OPTIONAL MATCH (c)-[:A_ATTRIBUT]->(a:Attribut)
                RETURN c.nom AS nom, coalesce(c.description, '') AS description,
                       collect(DISTINCT a.nom)[..20] AS attributs
                ORDER BY c.nom
                """
            )
            self._catalogue = [record.data() for record in records]
        self._catalogue_charge_a = time.time()
        return self._catalogue

    def resoudre_classes(self, question: str, limite: int = 5) -> list[dict]:
        question_normalisee = normaliser(question)
        question_tokens = tokens(question)
        candidats = []

        for classe in self._charger_catalogue():
            nom_normalise = normaliser(classe["nom"])
            nom_compact = nom_normalise.replace(" ", "")
            nom_tokens = tokens(classe["nom"])
            if not nom_compact:
                continue
            if nom_normalise in MOTS_AMBIGUS:
                continue

            exact = bool(re.search(rf"\b{re.escape(nom_normalise)}\b", question_normalisee))
            occurrences = len(
                re.findall(rf"\b{re.escape(nom_normalise)}\b", question_normalisee)
            )
            recouvrement = len(question_tokens & nom_tokens) / max(1, len(nom_tokens))
            similarite = max(
                SequenceMatcher(None, nom_compact, mot.replace(" ", "")).ratio()
                for mot in [question_normalisee, *question_normalisee.split()]
            )
            score = 1.0 if exact else (0.70 * recouvrement + 0.30 * similarite)

            description_tokens = tokens(classe.get("description", ""))
            if description_tokens:
                score += min(0.10, len(question_tokens & description_tokens) * 0.02)
            if score >= 0.48:
                candidats.append({
                    "nom": classe["nom"],
                    "score": round(min(score, 1.0), 4),
                    "exact": exact,
                    "occurrences": occurrences,
                    "nom_normalise": nom_normalise,
                })

        exacts = [c for c in candidats if c["exact"]]
        if exacts:
            candidats = [
                c for c in candidats
                if not c["exact"] or c["occurrences"] > 1 or not any(
                    c["nom_normalise"] != autre["nom_normalise"]
                    and re.search(rf"\b{re.escape(c['nom_normalise'])}\b", autre["nom_normalise"])
                    for autre in exacts
                )
            ]
        candidats.sort(key=lambda c: (-c["score"], -len(c["nom_normalise"]), c["nom"]))
        return [{"nom": c["nom"], "score": c["score"]} for c in candidats[:limite]]

    @staticmethod
    def determiner_mode(question: str) -> str:
        q = normaliser(question)
        mots_structure = {
            "attribut", "attributs", "type", "types", "heritage", "herite",
            "parent", "enfant", "relation", "relations", "cardinalite", "chemin",
            "compose", "composition", "association", "agregation", "voisin",
        }
        mots_document = {
            "procedure", "proceder", "comment", "regle", "consigne", "fiche",
            "documentation", "explique", "expliquer", "definition", "fonctionnement",
            "metier", "utilise", "utilisee", "utiliser",
        }
        ts = set(q.split())
        structure = bool(ts & mots_structure)
        document = bool(ts & mots_document)
        if structure and not document:
            return "STRUCTURE"
        if document and not structure:
            return "DOCUMENTAIRE"
        return "HYBRIDE"

    def _construire_sous_graphe(self, classes_racines: list[str]) -> dict:
        if not classes_racines:
            return {"classes": [], "attributs": [], "relations": [], "documents": []}

        with self.driver.session() as session:
            classes = [r.data() for r in session.run(
                """
                UNWIND $racines AS racine
                MATCH (c:Classe {nom: racine})
                OPTIONAL MATCH (c)-[:HERITE_DE|COMPOSE_DE|ASSOCIE_A|AGREGE]-(v:Classe)
                WITH collect(DISTINCT c) + collect(DISTINCT v) AS noeuds
                UNWIND noeuds AS n
                WITH DISTINCT n WHERE n IS NOT NULL
                RETURN n.nom AS nom, coalesce(n.description, '') AS description,
                       n.nom IN $racines AS racine
                ORDER BY racine DESC, nom LIMIT 40
                """,
                racines=classes_racines,
            )]
            perimetre = [c["nom"] for c in classes]

            attributs = [r.data() for r in session.run(
                """
                UNWIND $classes AS nom
                MATCH (c:Classe {nom: nom})-[:A_ATTRIBUT]->(a:Attribut)
                OPTIONAL MATCH (a)-[:EST_DE_TYPE]->(t)
                RETURN c.nom AS classe, a.nom AS attribut, labels(t)[0] AS categorie_type,
                       t.nom AS type, properties(a) AS proprietes
                ORDER BY classe, attribut LIMIT 250
                """,
                classes=perimetre,
            )]

            relations = [r.data() for r in session.run(
                """
                MATCH (a:Classe)-[r:HERITE_DE|COMPOSE_DE|ASSOCIE_A|AGREGE]->(b:Classe)
                WHERE a.nom IN $classes AND b.nom IN $classes
                RETURN a.nom AS source, type(r) AS type, b.nom AS cible,
                       properties(r) AS proprietes
                ORDER BY source, type, cible LIMIT 250
                """,
                classes=perimetre,
            )]

            documents = [r.data() for r in session.run(
                """
                MATCH (d:Document)-[:DECRIT]->(c:Classe)
                WHERE c.nom IN $classes
                RETURN DISTINCT d.id AS id, d.titre AS titre, d.source AS source,
                                c.nom AS classe
                ORDER BY classe, titre LIMIT 100
                """,
                classes=perimetre,
            )]

        return {
            "classes": classes,
            "attributs": attributs,
            "relations": relations,
            "documents": documents,
        }

    @staticmethod
    def _selectionner_concepts(
        question: str,
        concepts: list[dict],
        classes_racines: list[str],
        limite: int = 3,
    ) -> list[str]:
        q = normaliser(question)
        ts = tokens(question)
        classes = {normaliser(nom) for nom in classes_racines}
        candidats = []
        for concept in concepts:
            formulations = [concept.get("nom", ""), *(concept.get("aliases") or [])]
            formulations_normalisees = [normaliser(x) for x in formulations if x]
            exact = any(
                re.search(rf"\b{re.escape(formulation)}\b", q)
                for formulation in formulations_normalisees
            )
            recouvrement = max(
                (len(ts & tokens(formulation)) / max(1, len(tokens(formulation))))
                for formulation in formulations
            )
            classes_concept = {
                normaliser(nom) for nom in concept.get("classes_arianes", [])
            }
            score = (1.0 if exact else 0.7 * recouvrement)
            if classes & classes_concept:
                score += 0.35
            if score >= 0.55:
                candidats.append((min(score, 1.0), concept["id"]))
        candidats.sort(key=lambda item: (-item[0], item[1]))
        return [identifiant for _, identifiant in candidats[:limite]]

    def _construire_graphe_metier(
        self,
        question: str,
        classes_racines: list[str],
    ) -> dict:
        vide = {"concepts_racines": [], "concepts": [], "relations": []}
        with self.driver.session() as session:
            concepts = [
                record.data()
                for record in session.run(
                    """
                    MATCH (c:ConceptMetier)
                    OPTIONAL MATCH (c)-[:REPRESENTE_PAR]->(classe:Classe)
                    RETURN c.id AS id, c.nom AS nom, c.aliases AS aliases,
                           c.description AS description,
                           collect(DISTINCT classe.nom) AS classes_arianes
                    ORDER BY c.nom
                    """
                )
            ]
            racines = self._selectionner_concepts(
                question,
                concepts,
                classes_racines,
            )
            if not racines:
                return vide
            noeuds = [
                record.data()
                for record in session.run(
                    """
                    UNWIND $racines AS id
                    MATCH (racine:ConceptMetier {id: id})
                    OPTIONAL MATCH (racine)-[:RELATION_METIER]-(voisin:ConceptMetier)
                    WITH collect(DISTINCT racine) + collect(DISTINCT voisin) AS concepts
                    UNWIND concepts AS c
                    WITH DISTINCT c WHERE c IS NOT NULL
                    OPTIONAL MATCH (c)-[:REPRESENTE_PAR]->(classe:Classe)
                    OPTIONAL MATCH (c)-[:DOCUMENTE_PAR]->(document:Document)
                    RETURN c.id AS id, c.nom AS nom, c.description AS description,
                           collect(DISTINCT classe.nom) AS classes_arianes,
                           collect(DISTINCT document.titre) AS documents,
                           c.id IN $racines AS racine
                    ORDER BY racine DESC, nom LIMIT 30
                    """,
                    racines=racines,
                )
            ]
            ids = [noeud["id"] for noeud in noeuds]
            relations = [
                record.data()
                for record in session.run(
                    """
                    MATCH (a:ConceptMetier)-[r:RELATION_METIER]->(b:ConceptMetier)
                    WHERE a.id IN $ids AND b.id IN $ids
                    RETURN a.id AS source, r.type AS type, b.id AS cible,
                           r.preuve AS preuve
                    ORDER BY source, type, cible LIMIT 100
                    """,
                    ids=ids,
                )
            ]
        return {
            "concepts_racines": racines,
            "concepts": noeuds,
            "relations": relations,
        }

    def _chercher_chunks(self, question: str, classes: list[str], limite: int = 8) -> list[dict]:
        vecteur = self.embeddings.embed_query(question)
        candidats = {}

        with self.driver.session() as session:
            # Signal sémantique, limité au périmètre du sous-graphe lorsqu'il existe.
            semantiques = session.run(
                """
                MATCH (chunk:Chunk)-[:APPARTIENT_A]->(d:Document)
                OPTIONAL MATCH (d)-[:DECRIT]->(c:Classe)
                WHERE size($classes) = 0 OR c.nom IN $classes
                WITH chunk, d, c, vector.similarity.cosine(chunk.embedding, $vecteur) AS score
                RETURN chunk.id AS chunk_id, chunk.texte AS texte, chunk.position AS position,
                       d.id AS document, d.titre AS titre, c.nom AS classe, score
                ORDER BY score DESC LIMIT 30
                """,
                classes=classes,
                vecteur=vecteur,
            )
            for rang, record in enumerate(semantiques, 1):
                item = record.data()
                item["score_semantique"] = item.pop("score")
                if item["score_semantique"] < 0.65:
                    continue
                item["score_fusion"] = 1 / (60 + rang)
                candidats[item["chunk_id"]] = item

            # Signal lexical pour les noms, acronymes et termes métier exacts.
            try:
                lexicaux = session.run(
                    """
                    CALL db.index.fulltext.queryNodes('chunk_fulltext', $question)
                    YIELD node, score
                    MATCH (node)-[:APPARTIENT_A]->(d:Document)
                    OPTIONAL MATCH (d)-[:DECRIT]->(c:Classe)
                    WHERE size($classes) = 0 OR c.nom IN $classes
                    RETURN node.id AS chunk_id, node.texte AS texte, node.position AS position,
                           d.id AS document, d.titre AS titre, c.nom AS classe, score
                    ORDER BY score DESC LIMIT 30
                    """,
                    question=question,
                    classes=classes,
                )
                for rang, record in enumerate(lexicaux, 1):
                    item = record.data()
                    # Sans classe résolue, un résultat lexical seul est trop fragile :
                    # il doit aussi avoir franchi le seuil sémantique.
                    if not classes and item["chunk_id"] not in candidats:
                        continue
                    existant = candidats.setdefault(item["chunk_id"], item)
                    existant["score_lexical"] = item["score"]
                    existant["score_fusion"] = existant.get("score_fusion", 0) + 1 / (60 + rang)
                    existant.pop("score", None)
            except Exception:
                # L'index plein texte est optionnel pendant une migration.
                pass

        if not classes:
            # Une recherche globale doit être confirmée par les deux signaux.
            # Les cosinus seuls sont élevés même pour certaines questions hors domaine.
            candidats = {
                identifiant: item
                for identifiant, item in candidats.items()
                if item.get("score_lexical", 0) >= 2.0
            }

        resultat = sorted(candidats.values(), key=lambda x: -x.get("score_fusion", 0))[:limite]
        for item in resultat:
            item["citation"] = f"{item['titre']} — passage {item['position'] + 1}"
        return resultat

    def retrieve(self, question: str, historique: list[dict[str, str]] | None = None) -> dict:
        dernier_contexte = ""
        for message in reversed(historique or []):
            if message.get("role") == "user":
                dernier_contexte = message.get("content", "")
                break
        question_contextuelle = f"{dernier_contexte}\n{question}".strip() if dernier_contexte else question

        entites = self.resoudre_classes(question_contextuelle)
        if entites and entites[0]["score"] >= 0.90:
            seuil_racine = entites[0]["score"] - 0.05
        else:
            seuil_racine = 0.55
        racines = [e["nom"] for e in entites if e["score"] >= seuil_racine][:3]
        sous_graphe = self._construire_sous_graphe(racines)
        graphe_metier = self._construire_graphe_metier(question_contextuelle, racines)
        perimetre = [c["nom"] for c in sous_graphe["classes"]]
        mode = self.determiner_mode(question_contextuelle)
        chunks = [] if mode == "STRUCTURE" else self._chercher_chunks(question_contextuelle, perimetre)

        return {
            "question": question,
            "question_contextuelle": question_contextuelle,
            "mode": mode,
            "entites_candidates": entites,
            "classes_racines": racines,
            "sous_graphe": sous_graphe,
            "graphe_metier": graphe_metier,
            "chunks": chunks,
            "citations": list(dict.fromkeys(c["citation"] for c in chunks)),
        }

    @staticmethod
    def contexte_pour_llm(resultat: dict) -> str:
        copie = dict(resultat)
        copie.pop("question_contextuelle", None)
        return json.dumps(copie, ensure_ascii=False, indent=2)
