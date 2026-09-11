import json
import logging
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher


RELATIONS_STRUCTURELLES = ["HERITE_DE", "COMPOSE_DE", "ASSOCIE_A", "AGREGE"]
logger = logging.getLogger(__name__)
MOTS_AMBIGUS = {
    "a", "au", "aux", "ce", "ces", "dans", "de", "des", "du", "en", "est",
    "et", "la", "le", "les", "ou", "par", "pour", "que", "qui", "son", "sur",
    "un", "une",
}

MODES_SOURCES = {
    "STRUCTURE": {"uml": True, "documents": False, "metier": False, "chemin": False, "chemin_uml": False},
    "DOCUMENTAIRE": {"uml": False, "documents": True, "metier": False, "chemin": False, "chemin_uml": False},
    "METIER": {"uml": False, "documents": False, "metier": True, "chemin": False, "chemin_uml": False},
    "CHEMIN_METIER": {"uml": False, "documents": False, "metier": True, "chemin": True, "chemin_uml": False},
    "CHEMIN_UML": {"uml": True, "documents": False, "metier": False, "chemin": False, "chemin_uml": True},
    "HYBRIDE": {"uml": False, "documents": True, "metier": True, "chemin": False, "chemin_uml": False},
}


def normaliser(texte: str) -> str:
    texte = (texte or "").replace("œ", "oe").replace("Œ", "OE")
    texte = texte.replace("æ", "ae").replace("Æ", "AE")
    texte = re.sub(r"(?<=[A-ZÀ-Ý])(?=[A-ZÀ-Ý][a-zà-ÿ])", " ", texte or "")
    texte = re.sub(r"(?<=[a-zà-ÿ0-9])(?=[A-ZÀ-Ý])", " ", texte or "")
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", texte))


def tokens(texte: str) -> set[str]:
    return {t for t in normaliser(texte).split() if len(t) >= 2}


class GraphRAGRetriever:
    """Construit un contexte GraphRAG déterministe et entièrement sourcé."""

    def __init__(self, driver, embeddings, cache_seconds: int = 300, reranker=None):
        self.driver = driver
        self.embeddings = embeddings
        self.cache_seconds = cache_seconds
        self._catalogue = []
        self._catalogue_charge_a = 0.0
        self.reranker = reranker or self._charger_reranker_optionnel()

    @staticmethod
    def _necessite_contexte(question: str) -> bool:
        """Détecte une relance qui dépend réellement de la question précédente."""
        q = normaliser(question)
        if re.search(r"\b(?:la classe|classe uml|du concept|le concept)\s+[a-z0-9]", q):
            return False
        return bool(
            re.search(r"^(et|sinon|aussi|pour lui|pour elle|qu en est il)\b", q)
            or re.search(
                r"\b(ce dernier|cette derniere|celui ci|celle ci|ses attributs|"
                r"ses relations|son fonctionnement|sa definition)\b",
                q,
            )
        )

    @staticmethod
    def _charger_reranker_optionnel():
        chemin = os.getenv("RERANKER_MODEL_PATH", "").strip()
        if not chemin:
            return None
        try:
            from ml.reranker import LinearReranker

            modele = LinearReranker.load(chemin)
            logger.info("Reranker ML chargé depuis %s", chemin)
            return modele
        except Exception as exc:
            logger.warning("Reranker ML inutilisable, classement standard conservé : %s", exc)
            return None

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
        uniques = []
        deja_vus = set()
        for candidat in candidats:
            cle = candidat["nom_normalise"]
            if cle in deja_vus:
                continue
            deja_vus.add(cle)
            uniques.append({"nom": candidat["nom"], "score": candidat["score"]})
        return uniques[:limite]

    @staticmethod
    def analyser_question(question: str) -> dict:
        """Classe l'intention sans dépendre d'une classe ou d'un concept précis."""
        q = normaliser(question)
        mots = set(q.split())
        motifs_chemin = {
            "quel chemin", "un chemin", "le chemin", "chemin entre", "plus court chemin",
            "relie", "relier", "parcours entre",
            "relation indirecte", "connecte", "connexion entre", "entre deux concepts",
        }
        explicite_uml = any(x in q for x in (
            "uml", "metamodele", "meta modele", "classe arianes", "graphe structurel",
        ))
        explicite_metier = any(x in q for x in (
            "graphe metier", "relation metier", "relations metier",
            "concept metier", "concepts metier", "sous graphe metier",
        ))
        mention_classe = bool(mots & {"classe", "classes", "sousclasse", "superclasse"})
        structure = bool(mots & {
            "attribut", "attributs", "heritage", "herite", "heriter", "parent",
            "heritent", "enfant", "sousclasse", "superclasse", "cardinalite",
            "association", "associe", "associee", "associees", "agregation",
            "composition",
        }) or bool(re.search(r"\b(types?|classes?)\s+(?:de|du|d)\b", q)) or (
            mention_classe and bool(mots & {
                "relation", "relations", "directe", "directes", "compose",
                "composent", "type", "types",
            })
        )
        documentaire_fort = bool(mots & {
            "procedure", "proceder", "comment", "etape", "etapes", "regle", "regles",
            "consigne", "fiche", "documentation", "fonctionnement",
            "creer", "creation", "construire", "renseigner", "modifier", "modification",
            "supprimer", "appliquer", "expliquer", "explique",
        }) or "comment faire" in q
        documentaire = documentaire_fort or any(x in q for x in ("qu est ce", "c est quoi"))
        demande_sous_graphe_uml = explicite_uml and (
            "sous graphe" in q
            or "deux niveaux" in q
            or "2 niveaux" in q
            or "voisinage" in q
        )

        # Une mention explicite de « classe » vise le modèle UML par défaut.
        # Une demande de fiche, procédure ou fonctionnement reste documentaire.
        if mention_classe and not explicite_metier:
            structure = True
            if not documentaire_fort:
                documentaire = False
        metier = explicite_metier or bool(mots & {
            "rattache", "rattachee", "commande", "commandes", "commandee", "commandees",
            "localise", "localisee",
            "impacte", "protege", "utilise", "compose",
        }) or "relations directes" in q

        if demande_sous_graphe_uml:
            # « classes reliées au deuxième niveau » décrit un voisinage autour
            # d'une racine, pas un chemin entre deux extrémités.
            mode = "STRUCTURE"
        elif any(motif in q for motif in motifs_chemin):
            mode = "CHEMIN_UML" if explicite_uml else "CHEMIN_METIER"
        elif explicite_uml and (explicite_metier or documentaire_fort):
            mode = "HYBRIDE"
        elif explicite_uml:
            mode = "STRUCTURE"
        elif explicite_metier and documentaire:
            mode = "HYBRIDE"
        elif structure and documentaire:
            mode = "HYBRIDE"
        elif structure:
            mode = "STRUCTURE"
        elif documentaire and metier:
            mode = "HYBRIDE"
        elif documentaire:
            mode = "DOCUMENTAIRE"
        elif metier:
            mode = "METIER"
        else:
            # Une question générale cherche d'abord une définition dans le corpus.
            mode = "DOCUMENTAIRE"
        sources = dict(MODES_SOURCES[mode])
        if mode == "HYBRIDE":
            # HYBRIDE signifie union des intentions réellement détectées,
            # et non consultation systématique de toutes les couches.
            sources = {
                "uml": structure or explicite_uml,
                "documents": documentaire,
                "metier": metier or explicite_metier,
                "chemin": False,
                "chemin_uml": False,
            }
        return {"mode": mode, "sources": sources}

    @staticmethod
    def determiner_mode(question: str) -> str:
        """Compatibilité : retourne seulement le nom du mode de retrieval."""
        return GraphRAGRetriever.analyser_question(question)["mode"]

    def _construire_chemin_metier(
        self,
        question: str,
        classes_racines: list[str],
        profondeur_max: int = 5,
    ) -> dict:
        """Retourne le plus court chemin métier validé entre deux concepts cités."""
        vide = {
            "demande": True,
            "depart": None,
            "arrivee": None,
            "trouve": False,
            "concepts": [],
            "relations": [],
        }
        with self.driver.session() as session:
            concepts = [
                record.data()
                for record in session.run(
                    """
                    MATCH (c:ConceptMetier)
                    WHERE coalesce(c.actif, c.valide, false) AND coalesce(c.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
                    OPTIONAL MATCH (c)-[:REPRESENTE_PAR]->(classe:Classe)
                    RETURN c.id AS id, c.nom AS nom, c.aliases AS aliases,
                           c.description AS description,
                           collect(DISTINCT classe.nom) AS classes_arianes
                    ORDER BY c.nom
                    """
                )
            ]
            extremites = self._selectionner_extremites_chemin(
                question, concepts, classes_racines
            )
            if len(extremites) < 2:
                vide["concepts_detectes"] = extremites
                return vide

            depart, arrivee = extremites
            resultat = session.run(
                """
                MATCH (depart:ConceptMetier {id: $depart})
                MATCH (arrivee:ConceptMetier {id: $arrivee})
                MATCH chemin = shortestPath(
                    (depart)-[:RELATION_METIER*1..5]-(arrivee)
                )
                WHERE all(r IN relationships(chemin) WHERE coalesce(r.actif, r.valide, false)
                    AND coalesce(r.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE'])
                  AND all(n IN nodes(chemin) WHERE coalesce(n.actif, n.valide, false)
                    AND coalesce(n.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE'])
                RETURN [n IN nodes(chemin) | {
                    id: n.id, nom: n.nom, description: coalesce(n.description, '')
                }] AS concepts,
                [r IN relationships(chemin) | {
                    source: startNode(r).id, type: r.type, cible: endNode(r).id,
                    preuve: coalesce(r.preuve, ''),
                    document: coalesce(r.source_document, ''),
                    lignes: coalesce(r.lignes, ''),
                    chunk_ids: coalesce(r.chunk_ids, []),
                    condition: coalesce(r.condition, ''),
                    exception: coalesce(r.exception, ''),
                    statut: coalesce(r.statut, 'PROBABLE'),
                    score_confiance: coalesce(r.score_confiance, 0.0),
                    niveau_validation: coalesce(r.niveau_validation, 'DOCUMENTAIRE'),
                    validation_experte: coalesce(r.validation_experte, false),
                    avertissements: coalesce(r.avertissements, []),
                    validation: coalesce(r.validation, '')
                }] AS relations,
                length(chemin) AS longueur
                """,
                depart=depart,
                arrivee=arrivee,
            ).single()
        if not resultat:
            return {**vide, "depart": depart, "arrivee": arrivee}
        donnees = resultat.data() if hasattr(resultat, "data") else dict(resultat)
        return {
            "demande": True,
            "depart": depart,
            "arrivee": arrivee,
            "trouve": True,
            "longueur": donnees["longueur"],
            "concepts": donnees["concepts"],
            "relations": donnees["relations"],
            "profondeur_max": profondeur_max,
        }

    def _construire_chemin_uml(
        self,
        classes_racines: list[str],
        question: str = "",
        profondeur_max: int = 6,
        limite_candidats: int = 10,
    ) -> dict:
        """Retourne plusieurs chemins UML orientés, filtrés et classés localement."""
        vide = {
            "demande": True,
            "depart": classes_racines[0] if classes_racines else None,
            "arrivee": classes_racines[1] if len(classes_racines) > 1 else None,
            "trouve": False,
            "classes": [],
            "relations": [],
            "profondeur_max": profondeur_max,
            "candidats": [],
        }
        if len(classes_racines) < 2:
            mots_techniques = {
                "classe", "classes", "chemin", "uml", "etablir", "etablis",
                "trouver", "trouve", "relier", "relie", "entre", "vers",
                "depuis", "partir", "peut", "possible", "plusieurs", "sauts",
            }
            termes_racines = {
                mot for racine in classes_racines for mot in tokens(racine)
            }
            termes = [
                mot for mot in normaliser(question).split()
                if len(mot) >= 4
                and mot not in mots_techniques
                and mot not in termes_racines
                and mot not in MOTS_AMBIGUS
            ]
            suggestions = []
            for classe in self._charger_catalogue():
                nom_normalise = normaliser(classe.get("nom", ""))
                correspondances = [terme for terme in termes if terme in nom_normalise.split()]
                if correspondances and classe.get("nom") not in classes_racines:
                    commence = any(nom_normalise.startswith(terme) for terme in correspondances)
                    suggestions.append((not commence, len(nom_normalise), classe["nom"]))
            suggestions = [nom for _, _, nom in sorted(set(suggestions))[:8]]
            return {
                **vide,
                "classes_detectees": classes_racines,
                "classes_suggerees": suggestions,
            }

        depart, arrivee = classes_racines[:2]
        profondeur_max = max(1, min(int(profondeur_max), 8))
        with self.driver.session() as session:
            resultats = session.run(
                f"""
                MATCH (depart:Classe {{nom: $depart}})
                MATCH (arrivee:Classe {{nom: $arrivee}})
                MATCH chemin =
                    (depart)-[:HERITE_DE|COMPOSE_DE|ASSOCIE_A|AGREGE*1..{profondeur_max}]-(arrivee)
                WHERE all(n IN nodes(chemin)
                    WHERE single(m IN nodes(chemin) WHERE m = n))
                RETURN [n IN nodes(chemin) | {{
                           nom: n.nom,
                           description: coalesce(n.description, ''),
                           abstraite: coalesce(n.abstraite, false)
                       }}] AS classes,
                       [r IN relationships(chemin) | {{
                           source: startNode(r).nom,
                           type: type(r),
                           cible: endNode(r).nom,
                           proprietes: properties(r)
                       }}] AS relations,
                       length(chemin) AS longueur
                ORDER BY longueur
                LIMIT 80
                """,
                depart=depart,
                arrivee=arrivee,
            )
            chemins_bruts = [r.data() for r in resultats]
        if not chemins_bruts:
            return vide

        bonus_motifs = {
            ("HERITE_DE_INVERSE", "ASSOCIE_A_DIRECT"): 1.0,
            ("ASSOCIE_A_DIRECT", "HERITE_DE_INVERSE"): 1.0,
            ("HERITE_DE_INVERSE", "COMPOSE_DE_DIRECT"): 0.7,
            ("COMPOSE_DE_DIRECT", "ASSOCIE_A_DIRECT"): 0.5,
            ("COMPOSE_DE_DIRECT", "COMPOSE_DE_DIRECT"): 0.25,
        }
        termes_generiques = (
            "ressource", "implantation abstraite", "element externe", "objet abstrait"
        )
        termes_question = tokens(question) - MOTS_AMBIGUS
        candidats = []
        signatures = set()
        for donnees in chemins_bruts:
            classes = donnees.get("classes", [])
            relations = donnees.get("relations", [])
            signature = tuple(
                (r.get("source"), r.get("type"), r.get("cible")) for r in relations
            )
            if not signature or signature in signatures:
                continue
            signatures.add(signature)
            penalite_generique = 0.0
            bonus_semantique = 0.0
            for classe in classes[1:-1]:
                nom_normalise = normaliser(classe.get("nom", ""))
                if classe.get("abstraite") or any(t in nom_normalise for t in termes_generiques):
                    penalite_generique += 0.75
                bonus_semantique += min(
                    0.30,
                    0.05 * len(termes_question & tokens(classe.get("description", ""))),
                )
            relations_annotees = []
            for index, relation in enumerate(relations):
                relation = dict(relation)
                parcours_source = classes[index]["nom"]
                parcours_cible = classes[index + 1]["nom"]
                relation["parcours_source"] = parcours_source
                relation["parcours_cible"] = parcours_cible
                relation["sens_parcours"] = (
                    "DIRECT" if relation.get("source") == parcours_source else "INVERSE"
                )
                relations_annotees.append(relation)

            nombre_inverses = sum(
                r["sens_parcours"] == "INVERSE" for r in relations_annotees
            )
            nombre_roles = sum(
                bool((r.get("proprietes") or {}).get("role")) for r in relations_annotees
            )
            signatures_relations = [
                f"{r.get('type')}_{r.get('sens_parcours')}" for r in relations_annotees
            ]
            bonus_coherence = sum(
                bonus_motifs.get((a, b), 0.0)
                for a, b in zip(signatures_relations, signatures_relations[1:])
            )
            types_chemin = [r.get("type") for r in relations_annotees]
            pont_ontologique = (
                len(types_chemin) == 3
                and types_chemin[0] == "HERITE_DE"
                and types_chemin[1] == "ASSOCIE_A"
                and types_chemin[2] == "HERITE_DE"
            )
            chaine_heritage = bool(types_chemin) and all(
                type_relation == "HERITE_DE" for type_relation in types_chemin
            )
            # Ce motif relie deux familles de classes par une association entre
            # leurs spécialisations/abstractions. Il explique généralement mieux
            # un lien conceptuel qu'un détour par des objets de localisation.
            if pont_ontologique:
                bonus_coherence += 3.0
            changements = sum(
                a.split("_INVERSE")[0].split("_DIRECT")[0]
                != b.split("_INVERSE")[0].split("_DIRECT")[0]
                for a, b in zip(signatures_relations, signatures_relations[1:])
            )
            score = (
                len(relations_annotees)
                + penalite_generique
                + 0.25 * nombre_inverses
                + 0.20 * changements
                - 0.40 * nombre_roles
                - bonus_coherence
                - bonus_semantique
            )
            candidats.append({
                "classes": classes,
                "relations": relations_annotees,
                "longueur": len(relations_annotees),
                "score": round(score, 3),
                "penalite_classes_generiques": round(penalite_generique, 3),
                "relations_inverses": nombre_inverses,
                "relations_avec_role": nombre_roles,
                "bonus_coherence": round(bonus_coherence, 3),
                "pont_ontologique": pont_ontologique,
                "chaine_heritage": chaine_heritage,
                "support_semantique": round(bonus_semantique, 3),
            })

        candidats.sort(key=lambda c: (c["score"], c["longueur"]))
        candidats = candidats[:limite_candidats]
        if not candidats:
            return vide
        for index, candidat in enumerate(candidats, start=1):
            candidat["id"] = f"CHEMIN_{index}"
        # Un chemin peut être valide dans Neo4j tout en n'étant qu'un détour
        # technique. Au-delà de six relations ou d'un score élevé, les noms UML
        # seuls ne permettent plus de lui attribuer un sens fiable. Ces chemins
        # restent visibles dans `candidats`, mais ne sont pas proposés comme réponse.
        admissibles = []
        for candidat in candidats:
            motif_fort = (
                candidat["longueur"] <= 2
                or candidat.get("pont_ontologique", False)
                or candidat.get("chaine_heritage", False)
                or candidat.get("support_semantique", 0) >= 0.30
            )
            if candidat["longueur"] <= 6 and candidat["score"] <= 7.0 and motif_fort:
                admissibles.append(candidat)
        if not admissibles:
            return {
                **vide,
                "depart": depart,
                "arrivee": arrivee,
                "candidats": candidats,
                "aucun_pertinent": True,
                "methode_selection": "garde_deterministe",
            }
        selection = admissibles[0]
        return {
            **vide,
            "trouve": True,
            "longueur": selection["longueur"],
            "classes": selection["classes"],
            "relations": selection["relations"],
            "score": selection["score"],
            "selection": selection["id"],
            "methode_selection": "score_deterministe",
            "candidats": admissibles,
            "candidats_ecartes": len(candidats) - len(admissibles),
        }

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
            intervalles_exacts = [
                (correspondance.start(), correspondance.end())
                for formulation in formulations_normalisees
                for correspondance in re.finditer(rf"\b{re.escape(formulation)}\b", q)
            ]
            exact = bool(intervalles_exacts)
            recouvrement = max(
                (len(ts & tokens(formulation)) / max(1, len(tokens(formulation))))
                for formulation in formulations
            )
            classes_concept = {
                normaliser(nom) for nom in concept.get("classes_arianes", [])
            }
            # Tolérance bornée aux fautes simples sur un alias ou un nom composé
            # réduit à son mot significatif (ex. « post » pour l'alias « poste »).
            # Les noms complets des sous-types ne sont pas comparés mot à mot afin
            # que « post » ne sélectionne pas tous les concepts commençant par Poste.
            formulations_courtes = [
                normaliser(x) for x in (concept.get("aliases") or []) if x
            ]
            nom_tokens = tokens(concept.get("nom", ""))
            if len(nom_tokens) == 1:
                formulations_courtes.append(next(iter(nom_tokens), ""))
            fuzzy = any(
                len(mot_question) >= 4 and len(formulation) >= 4
                and SequenceMatcher(None, mot_question, formulation).ratio() >= 0.86
                for mot_question in ts
                for formulation in formulations_courtes
            )
            score = (1.0 if exact else (0.82 if fuzzy else 0.7 * recouvrement))
            if classes & classes_concept:
                score += 0.35
            if score >= 0.55:
                candidats.append({
                    "score": min(score, 1.0),
                    "id": concept["id"],
                    "exact": exact,
                    "intervalles": intervalles_exacts,
                })

        exacts = [c for c in candidats if c["exact"]]
        if exacts:
            # Une mention précise remplace les concepts inclus dans la même portion
            # de texte : « poste d'aiguillage » écarte « poste » et les fuzzy.
            candidats = [
                candidat
                for candidat in exacts
                if any(
                    not any(
                        autre["id"] != candidat["id"]
                        and autre_debut <= debut
                        and autre_fin >= fin
                        and (autre_fin - autre_debut) > (fin - debut)
                        for autre in exacts
                        for autre_debut, autre_fin in autre["intervalles"]
                    )
                    for debut, fin in candidat["intervalles"]
                )
            ]

        candidats.sort(key=lambda item: (-item["score"], item["id"]))
        return [item["id"] for item in candidats[:limite]]

    @staticmethod
    def _selectionner_extremites_chemin(
        question: str,
        concepts: list[dict],
        classes_racines: list[str],
    ) -> list[str]:
        """Sélectionne deux mentions distinctes et privilégie les noms précis."""
        q = normaliser(question)
        mentions = []
        for concept in concepts:
            formulations = [concept.get("nom", ""), *(concept.get("aliases") or [])]
            for formulation in formulations:
                f = normaliser(formulation)
                if not f or f in MOTS_AMBIGUS:
                    continue
                for correspondance in re.finditer(rf"\b{re.escape(f)}\b", q):
                    nom_exact = normaliser(concept.get("nom", "")) == f
                    mentions.append((
                        correspondance.start(), correspondance.end(),
                        len(f), nom_exact, concept["id"],
                    ))

        mentions.sort(key=lambda m: (-m[2], -int(m[3]), m[0], m[4]))
        retenues = []
        intervalles = []
        for debut, fin, _, _, identifiant in mentions:
            if any(debut < autre_fin and fin > autre_debut for autre_debut, autre_fin in intervalles):
                continue
            retenues.append((debut, identifiant))
            intervalles.append((debut, fin))
            if len(retenues) == 2:
                break
        if len(retenues) == 2:
            return [identifiant for _, identifiant in sorted(retenues)]
        return GraphRAGRetriever._selectionner_concepts(
            question, concepts, classes_racines, limite=2
        )

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
                    WHERE coalesce(c.actif, c.valide, false) AND coalesce(c.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
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
                    WHERE coalesce(racine.actif, racine.valide, false)
                      AND coalesce(racine.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
                    OPTIONAL MATCH (racine)-[lien:RELATION_METIER]-(voisin:ConceptMetier)
                    WHERE coalesce(lien.actif, lien.valide, false)
                      AND coalesce(voisin.actif, voisin.valide, false)
                      AND coalesce(lien.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
                      AND coalesce(voisin.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
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
                    WHERE a.id IN $ids AND b.id IN $ids AND coalesce(r.actif, r.valide, false)
                      AND coalesce(a.actif, a.valide, false) AND coalesce(b.actif, b.valide, false)
                      AND coalesce(r.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
                      AND (a.id IN $racines OR b.id IN $racines)
                    RETURN a.id AS source, r.type AS type, b.id AS cible,
                           r.preuve AS preuve, r.source_document AS document,
                           r.lignes AS lignes, r.chunk_ids AS chunk_ids,
                           r.condition AS condition, r.exception AS exception,
                           coalesce(r.statut, 'PROBABLE') AS statut,
                           coalesce(r.score_confiance, 0.0) AS score_confiance,
                           coalesce(r.niveau_validation, 'DOCUMENTAIRE') AS niveau_validation,
                           coalesce(r.validation_experte, false) AS validation_experte,
                           coalesce(r.avertissements, []) AS avertissements,
                           r.validation AS validation
                    ORDER BY source, type, cible LIMIT 100
                    """,
                    ids=ids,
                    racines=racines,
                )
            ]
        return {
            "concepts_racines": racines,
            "concepts": noeuds,
            "relations": relations,
        }

    def _chercher_preuves_metier(self, graphe_metier: dict) -> list[dict]:
        ids = list(dict.fromkeys(
            ident for relation in graphe_metier.get("relations", [])
            for ident in (relation.get("chunk_ids") or [])
        ))[:6]
        if not ids:
            return []
        with self.driver.session() as session:
            chunks = [r.data() for r in session.run(
                "MATCH (c:Chunk)-[:APPARTIENT_A]->(d:Document) WHERE c.id IN $ids "
                "RETURN c.id AS chunk_id, c.texte AS texte, c.position AS position, "
                "d.id AS document, d.titre AS titre ORDER BY document, position", ids=ids
            )]
        for c in chunks:
            c["citation"] = f"{c['titre']} — passage {c['position'] + 1}"
            c["origine_retrieval"] = "preuve_graphe_metier"
        return chunks

    def _chercher_chunks(self, question: str, classes: list[str], limite: int = 8) -> list[dict]:
        candidats = {}
        recherche_semantique_disponible = True
        termes_exacts = tokens(question) - MOTS_AMBIGUS - {
            "quoi", "definition", "signifie", "veut", "dire",
        }
        requete_lexicale = " ".join(sorted(termes_exacts)) or question

        try:
            vecteur = self.embeddings.embed_query(question)
        except Exception as exc:
            recherche_semantique_disponible = False
            vecteur = None
            logger.warning(
                "Embeddings Mistral indisponibles ; recherche lexicale seule : %s",
                exc,
            )

        with self.driver.session() as session:
            # Signal sémantique, limité au périmètre du sous-graphe lorsqu'il existe.
            if recherche_semantique_disponible:
                semantiques = session.run(
                    """
                    MATCH (chunk:Chunk)-[:APPARTIENT_A]->(d:Document)
                    OPTIONAL MATCH (d)-[:DECRIT]->(c:Classe)
                    WITH chunk, d, c
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
                    if item["score_semantique"] is None or item["score_semantique"] < 0.65:
                        continue
                    if item["chunk_id"] in candidats:
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
                    WITH node, score, d, c
                    WHERE size($classes) = 0 OR c.nom IN $classes
                    RETURN node.id AS chunk_id, node.texte AS texte, node.position AS position,
                           d.id AS document, d.titre AS titre, c.nom AS classe, score
                    ORDER BY score DESC LIMIT 30
                    """,
                    question=requete_lexicale,
                    classes=classes,
                )
                for rang, record in enumerate(lexicaux, 1):
                    item = record.data()
                    # Sans classe résolue, un résultat lexical seul est trop fragile :
                    # il doit aussi avoir franchi le seuil sémantique.
                    if not classes and item["chunk_id"] not in candidats:
                        correspondance_exacte = bool(
                            termes_exacts & tokens(item.get("texte", ""))
                        )
                        if item.get("score", 0) < 2.0 or not correspondance_exacte:
                            continue
                    existant = candidats.setdefault(item["chunk_id"], item)
                    if "score_lexical" in existant:
                        continue
                    existant["score_lexical"] = item["score"]
                    existant["score_fusion"] = existant.get("score_fusion", 0) + 1 / (60 + rang)
                    existant.pop("score", None)
            except Exception as exc:
                # L'index plein texte est optionnel pendant une migration.
                logger.warning("Recherche plein texte indisponible : %s", exc)

        if not classes:
            # Une recherche globale doit être confirmée par les deux signaux.
            # Les cosinus seuls sont élevés même pour certaines questions hors domaine.
            candidats = {
                identifiant: item
                for identifiant, item in candidats.items()
                if item.get("score_lexical", 0) >= 2.0
            }

        resultat = sorted(candidats.values(), key=lambda x: -x.get("score_fusion", 0))
        if self.reranker is not None:
            resultat = self.reranker.rerank(question, resultat)
        resultat = resultat[:limite]
        for item in resultat:
            item["citation"] = f"{item['titre']} — passage {item['position'] + 1}"
        return resultat

    def retrieve(self, question: str, historique: list[dict[str, str]] | None = None) -> dict:
        dernier_contexte = ""
        for message in reversed(historique or []):
            if message.get("role") == "user":
                dernier_contexte = message.get("content", "")
                break
        question_contextuelle = (
            f"{dernier_contexte}\n{question}".strip()
            if dernier_contexte and self._necessite_contexte(question)
            else question
        )

        routage = self.analyser_question(question_contextuelle)
        mode = routage["mode"]
        sources = routage["sources"]
        entites = self.resoudre_classes(question_contextuelle)
        if entites and entites[0]["score"] >= 0.90:
            seuil_racine = entites[0]["score"] - 0.05
        else:
            seuil_racine = 0.55
        racines = [e["nom"] for e in entites if e["score"] >= seuil_racine][:3]
        if mode == "CHEMIN_UML" and len(racines) >= 2:
            question_ordonnee = normaliser(question_contextuelle)
            racines.sort(
                key=lambda nom: (
                    question_ordonnee.find(normaliser(nom))
                    if normaliser(nom) in question_ordonnee
                    else len(question_ordonnee),
                    -len(normaliser(nom)),
                )
            )
        sous_graphe = (
            self._construire_sous_graphe(racines)
            if sources["uml"]
            else {"classes": [], "attributs": [], "relations": [], "documents": []}
        )
        # Pour les documents, limiter la recherche aux classes explicitement
        # résolues. Les voisins UML ne doivent pas polluer une procédure.
        perimetre = racines
        graphe_metier = (
            self._construire_graphe_metier(question_contextuelle, racines)
            if sources["metier"]
            else {"concepts_racines": [], "concepts": [], "relations": []}
        )
        chemin_metier = (
            self._construire_chemin_metier(question_contextuelle, racines)
            if sources["chemin"]
            else {"demande": False, "trouve": False, "concepts": [], "relations": []}
        )
        chemin_uml = (
            self._construire_chemin_uml(racines, question_contextuelle)
            if sources.get("chemin_uml")
            else {"demande": False, "trouve": False, "classes": [], "relations": []}
        )
        if sources["documents"]:
            try:
                chunks = self._chercher_chunks(
                    question_contextuelle,
                    perimetre,
                    limite=4,
                )
            except Exception as exc:
                if not graphe_metier.get("relations") and not chemin_metier.get("relations"):
                    raise
                logger.warning(
                    "Recherche vectorielle indisponible ; poursuite avec le graphe validé : %s",
                    exc,
                )
                chunks = []
        else:
            chunks = []
        graphe_preuves = {
            "relations": [
                *graphe_metier.get("relations", []),
                *chemin_metier.get("relations", []),
            ]
        }
        preuves = self._chercher_preuves_metier(graphe_preuves)
        ids_preuves = {c["chunk_id"] for c in preuves}
        chunks = (preuves + [c for c in chunks if c["chunk_id"] not in ids_preuves])[:12]

        return {
            "question": question,
            "question_contextuelle": question_contextuelle,
            "mode": mode,
            "routage": routage,
            "entites_candidates": entites,
            "classes_racines": racines,
            "sous_graphe": sous_graphe,
            "graphe_metier": graphe_metier,
            "chemin_metier": chemin_metier,
            "chemin_uml": chemin_uml,
            "chunks": chunks,
            "citations": list(dict.fromkeys(c["citation"] for c in chunks)),
        }

    @staticmethod
    def contexte_pour_llm(resultat: dict) -> str:
        copie = dict(resultat)
        copie.pop("question_contextuelle", None)
        return json.dumps(copie, ensure_ascii=False, indent=2)
