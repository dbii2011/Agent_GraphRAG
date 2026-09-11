import json
import logging
import os
import re
import time

import httpx
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from neo4j import GraphDatabase

from .retrieval import GraphRAGRetriever, normaliser


load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "60"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "60"))
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() in {"1", "true", "yes", "oui"}
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AgentLG")


class EmbeddingsIndisponibles:
    """Déclenche le fallback lexical lorsque Mistral embeddings n'est pas configuré."""

    def embed_query(self, _question: str):
        raise RuntimeError("Aucun fournisseur d'embeddings n'est configuré.")


class AgentLG:
    """Assistant Arianes fondé sur un pipeline GraphRAG contrôlé."""

    def __init__(self):
        if not NEO4J_PASSWORD:
            raise ValueError("NEO4J_PASSWORD est absent du fichier .env.")
        if not any((MISTRAL_API_KEY, GEMINI_API_KEY, GROQ_API_KEY)):
            raise ValueError("Aucune clé LLM (Mistral, Gemini ou Groq) n'est configurée.")

        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )
        self.llm = (
            ChatMistralAI(
                model=MODEL,
                api_key=MISTRAL_API_KEY,
                timeout=30,
                temperature=0,
            )
            if MISTRAL_API_KEY else None
        )
        self.embeddings = (
            MistralAIEmbeddings(model="mistral-embed", api_key=MISTRAL_API_KEY)
            if MISTRAL_API_KEY else EmbeddingsIndisponibles()
        )
        self.retriever = GraphRAGRetriever(self.driver, self.embeddings)

    def close(self):
        self.driver.close()

    def _invoquer_groq(self, messages: list[dict[str, str]]) -> str:
        """Appelle le modèle Groq hébergé avec une API compatible OpenAI."""
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY n'est pas configurée.")
        messages_compacts = self._compacter_messages_groq(messages)
        reponse = httpx.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages_compacts,
                "temperature": 0,
                "max_completion_tokens": 1600,
                "reasoning_effort": "low",
                "include_reasoning": False,
            },
            timeout=GROQ_TIMEOUT,
        )
        reponse.raise_for_status()
        donnees = reponse.json()
        choix = donnees.get("choices", [])
        contenu = choix[0].get("message", {}).get("content", "").strip() if choix else ""
        if not contenu:
            choix_unique = choix[0] if choix else {}
            usage = donnees.get("usage", {})
            raise RuntimeError(
                "Groq a retourné une réponse vide "
                f"(finish_reason={choix_unique.get('finish_reason')}, "
                f"completion_tokens={usage.get('completion_tokens')})."
            )
        logger.info("Réponse générée avec Groq (%s)", GROQ_MODEL)
        return contenu

    def _invoquer_gemini(self, messages: list[dict[str, str]]) -> str:
        """Appelle Gemini en convertissant les rôles vers son format natif."""
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY n'est pas configurée.")
        systeme = "\n\n".join(
            str(message.get("content", ""))
            for message in messages
            if message.get("role") == "system"
        )
        contenus = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            contenus.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": str(message.get("content", ""))}],
            })
        charge = {
            "contents": contenus,
            "generationConfig": {"temperature": 0, "maxOutputTokens": 1600},
        }
        if systeme:
            charge["system_instruction"] = {"parts": [{"text": systeme}]}
        reponse = httpx.post(
            f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent",
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=charge,
            timeout=GEMINI_TIMEOUT,
        )
        reponse.raise_for_status()
        donnees = reponse.json()
        candidats = donnees.get("candidates", [])
        parties = candidats[0].get("content", {}).get("parts", []) if candidats else []
        contenu = "".join(str(partie.get("text", "")) for partie in parties).strip()
        if not contenu:
            raise RuntimeError("Gemini a retourné une réponse vide.")
        logger.info("Réponse générée avec Gemini (%s)", GEMINI_MODEL)
        return contenu

    def fournisseurs_disponibles(self) -> dict[str, bool]:
        """Indique uniquement quelles clés sont configurées, sans les exposer."""
        return {
            "mistral": bool(MISTRAL_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "groq": bool(GROQ_API_KEY),
        }

    def _generer(self, provider: str, messages: list[dict[str, str]]) -> str:
        """Appelle exclusivement le fournisseur choisi par l'utilisateur."""
        if provider == "mistral":
            if self.llm is None:
                raise RuntimeError("MISTRAL_API_KEY n'est pas configurée.")
            resultat = self.llm.invoke(messages)
            return self._retirer_sources_visibles(resultat.content)
        if provider == "gemini":
            return self._retirer_sources_visibles(self._invoquer_gemini(messages))
        if provider == "groq":
            return self._retirer_sources_visibles(self._invoquer_groq(messages))
        raise ValueError(f"Fournisseur LLM non autorisé : {provider}")

    @staticmethod
    def _compacter_messages_groq(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Réduit le prompt sous les petits quotas Groq sans perdre les chunks finaux."""
        if not messages:
            return []

        compacts = []
        systeme = str(messages[0].get("content", ""))
        compacts.append({"role": "system", "content": systeme[:4500]})

        # Deux messages d'historique courts suffisent pour les relances simples.
        for message in messages[1:-1][-2:]:
            compacts.append({
                "role": message.get("role", "user"),
                "content": str(message.get("content", ""))[:1000],
            })

        dernier = str(messages[-1].get("content", ""))
        if len(dernier) > 12000:
            # Le début contient la question ; la fin contient généralement les chunks.
            dernier = dernier[:2500] + "\n\n[… contexte intermédiaire compacté …]\n\n" + dernier[-9400:]
        compacts.append({"role": messages[-1].get("role", "user"), "content": dernier})

        logger.info(
            "Contexte Groq compacté : %s → %s caractères",
            sum(len(str(m.get("content", ""))) for m in messages),
            sum(len(m["content"]) for m in compacts),
        )
        return compacts

    def _invoquer_ollama(self, messages: list[dict[str, str]]) -> str:
        """Appelle l'API locale Ollama avec les mêmes messages que Mistral."""
        if not OLLAMA_ENABLED:
            raise RuntimeError("Le secours Ollama est désactivé.")
        reponse = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        reponse.raise_for_status()
        contenu = reponse.json().get("message", {}).get("content", "").strip()
        if not contenu:
            raise RuntimeError("Ollama a retourné une réponse vide.")
        logger.info("Réponse générée localement avec Ollama (%s)", OLLAMA_MODEL)
        return contenu

    def _essayer_ollama(self, messages: list[dict[str, str]] | None) -> str | None:
        """Tente le modèle local sans masquer une éventuelle panne d'Ollama."""
        if not messages:
            return None
        try:
            return self._retirer_sources_visibles(self._invoquer_ollama(messages))
        except Exception as exc:
            logger.warning("Secours Ollama indisponible : %s", exc)
            return None

    def _essayer_modeles_secours(self, messages: list[dict[str, str]] | None) -> str | None:
        """Essaie Groq puis Ollama avec le même contexte GraphRAG."""
        if not messages:
            return None
        if GROQ_API_KEY:
            try:
                return self._retirer_sources_visibles(self._invoquer_groq(messages))
            except Exception as exc:
                logger.warning("Secours Groq indisponible : %s", exc)
        else:
            logger.info("Secours Groq ignoré : GROQ_API_KEY absente.")
        return self._essayer_ollama(messages)

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
    def _formater_chemin_uml(chemin: dict) -> str:
        """Formate le chemin structurel UML sans le confondre avec le métier."""
        depart = chemin.get("depart") or "la classe de départ"
        arrivee = chemin.get("arrivee") or "la classe d’arrivée"
        if not chemin.get("trouve"):
            if chemin.get("aucun_pertinent"):
                return (
                    f"Des chemins UML orientés existent entre **{depart}** et **{arrivee}**, "
                    "mais ils traversent trop de relations techniques ou de classes génériques. "
                    "Aucun chemin suffisamment pertinent ne peut donc être présenté sans "
                    "interprétation métier supplémentaire."
                )
            if len(chemin.get("classes_detectees", [])) < 2 and not chemin.get("arrivee"):
                detectees = chemin.get("classes_detectees", [])
                suggestions = chemin.get("classes_suggerees", [])
                if suggestions:
                    liste = ", ".join(f"**{nom}**" for nom in suggestions)
                    connue = (
                        f" La classe **{detectees[0]}** a bien été identifiée."
                        if detectees else ""
                    )
                    return (
                        "Il n’existe pas de classe UML portant exactement le nom demandé."
                        f"{connue} Classes proches disponibles : {liste}. "
                        "Précise laquelle doit servir de point de départ."
                    )
                return (
                    "Je n’ai pas pu identifier deux classes UML distinctes. "
                    "Précise la classe de départ et la classe d’arrivée."
                )
            return (
                f"Aucun chemin UML n’a été trouvé entre **{depart}** et **{arrivee}** "
                f"dans la limite de {chemin.get('profondeur_max', 8)} relations structurelles."
            )
        lignes = []
        for relation in chemin.get("relations", []):
            source = relation.get("parcours_source", relation.get("source"))
            cible = relation.get("parcours_cible", relation.get("cible"))
            type_relation = relation.get("type")
            if relation.get("sens_parcours") == "INVERSE":
                lignes.append(f"- **{source}** ← `{type_relation}` — **{cible}**")
            else:
                lignes.append(f"- **{source}** — `{type_relation}` → **{cible}**")
        nombre = len(lignes)
        return (
            f"Le chemin UML orienté retenu entre **{depart}** et **{arrivee}** comporte "
            f"{nombre} relation{'s' if nombre != 1 else ''} :\n\n" + "\n".join(lignes)
        )

    def _selectionner_chemin_uml_avec_llm(
        self, question: str, chemin: dict, provider: str
    ) -> dict:
        """Demande au LLM de classer des chemins existants sans pouvoir en inventer."""
        candidats = chemin.get("candidats", [])
        if len(candidats) <= 1:
            return chemin
        candidats_compacts = []
        for candidat in candidats:
            candidats_compacts.append({
                "id": candidat["id"],
                "score_local": candidat["score"],
                "pont_ontologique": candidat.get("pont_ontologique", False),
                "classes": [c.get("nom") for c in candidat.get("classes", [])],
                "relations": [
                    {
                        "source_uml": r.get("source"),
                        "type": r.get("type"),
                        "cible_uml": r.get("cible"),
                        "parcours_de": r.get("parcours_source", r.get("source")),
                        "parcours_vers": r.get("parcours_cible", r.get("cible")),
                        "sens_parcours": r.get("sens_parcours", "DIRECT"),
                        "role": (r.get("proprietes") or {}).get("role"),
                    }
                    for r in candidat.get("relations", [])
                ],
                "descriptions": [
                    {"nom": c.get("nom"), "description": str(c.get("description", ""))[:350]}
                    for c in candidat.get("classes", [])
                    if c.get("description")
                ],
            })
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu classes des chemins UML qui existent déjà dans Neo4j. "
                    "Choisis celui qui répond le mieux au sens de la question. Privilégie une "
                    "chaîne fonctionnelle compréhensible et pénalise les détours par des classes "
                    "abstraites ou génériques. Pour une question générale de connexion entre deux "
                    "classes, privilégie un candidat marqué pont_ontologique=true : il relie deux "
                    "familles UML par le motif héritage, association, héritage. Ne le privilégie "
                    "pas si la question demande explicitement une localisation ou un PK. "
                    "Tu n'as pas le droit de modifier, fusionner ou "
                    "inventer un chemin. Réponds uniquement avec son identifiant exact, par "
                    "exemple CHEMIN_2. Si aucun chemin n'est pertinent, réponds AUCUN."
                ),
            },
            {
                "role": "user",
                "content": f"Question : {question}\n\nCandidats :\n{json.dumps(candidats_compacts, ensure_ascii=False)}",
            },
        ]
        choix = self._generer(provider, messages).strip().upper()
        correspondance = re.fullmatch(r"(?:`|\*\*)?(CHEMIN_\d+)(?:`|\*\*)?[.!]?", choix)
        if not correspondance:
            if choix == "AUCUN":
                return {
                    **chemin,
                    "trouve": False,
                    "aucun_pertinent": True,
                    "methode_selection": "llm_aucun",
                }
            raise RuntimeError(f"Sélection de chemin invalide : {choix[:80]}")
        identifiant = correspondance.group(1)
        selection = next((c for c in candidats if c["id"] == identifiant), None)
        if selection is None:
            raise RuntimeError("Le LLM a sélectionné un chemin absent des candidats.")
        return {
            **chemin,
            "trouve": True,
            "classes": selection["classes"],
            "relations": selection["relations"],
            "longueur": selection["longueur"],
            "score": selection["score"],
            "selection": identifiant,
            "methode_selection": "llm_controle",
        }

    @staticmethod
    def _schema_depuis_retrieval(resultat: dict) -> dict | None:
        """Construit le petit graphe à afficher, sans demander sa structure au LLM."""
        chemin_uml = resultat.get("chemin_uml", {})
        chemin_metier = resultat.get("chemin_metier", {})
        if chemin_uml.get("trouve"):
            source = {"relations": chemin_uml.get("relations", []), "concepts": [
                {"id": classe.get("nom"), "nom": classe.get("nom")}
                for classe in chemin_uml.get("classes", [])
            ]}
        else:
            source = chemin_metier if chemin_metier.get("trouve") else resultat.get("graphe_metier", {})
        relations = source.get("relations", [])
        concepts = source.get("concepts", [])
        if not relations:
            return None
        racines = set(source.get("concepts_racines", []))

        # Le schéma intégré à une réponse doit rester synthétique. Le contexte
        # textuel conserve toutes les relations, mais la visualisation privilégie
        # celles qui touchent directement le concept demandé, puis les relations
        # les mieux validées.
        def priorite(relation: dict):
            touche_racine = (
                relation.get("source") in racines
                or relation.get("cible") in racines
            )
            statut = relation.get("statut", "VALIDE")
            return (
                0 if touche_racine else 1,
                0 if statut == "VALIDE" else 1,
                -float(relation.get("score_confiance", 0) or 0),
                str(relation.get("type", "")),
                str(relation.get("cible", "")),
            )

        relations_affichees = sorted(relations, key=priorite)
        ids_utiles = {
            identifiant
            for relation in relations_affichees
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
                for relation in relations_affichees
            ],
            "total_links": len(relations_affichees),
        }

    @staticmethod
    def _retour(texte: str, schema: dict | None, inclure_graphe: bool):
        return {"reponse": texte, "graphe": schema} if inclure_graphe else texte

    @staticmethod
    def _formater_relations_secours(question: str, graphe: dict) -> str | None:
        """Produit une réponse lisible depuis Neo4j lorsque le LLM est indisponible."""
        concepts = {
            concept.get("id"): concept.get("nom") or concept.get("id", "").replace("_", " ")
            for concept in graphe.get("concepts", [])
        }
        relations = graphe.get("relations", [])
        if not relations:
            return None

        question_simple = question.lower()
        if "command" in question_simple and "poste" in question_simple:
            equipements = []
            for relation in relations:
                if (
                    relation.get("type") == "EST_COMMANDE_PAR"
                    and "poste" in str(relation.get("cible", ""))
                ):
                    nom = concepts.get(relation.get("source"), relation.get("source", ""))
                    if nom and nom not in equipements:
                        equipements.append(nom)
            if equipements:
                enumeration = ", ".join(equipements[:-1])
                if len(equipements) > 1:
                    enumeration += f" et {equipements[-1]}"
                else:
                    enumeration = equipements[0]
                sujet = (
                    "les équipements commandés sont"
                    if len(equipements) > 1
                    else "l’équipement commandé est"
                )
                return (
                    "Selon les relations validées du graphe, "
                    f"{sujet} **{enumeration}**."
                )

        formulations = {
            "EST_COMMANDE_PAR": "est commandé par",
            "RATTACHE_A": "est rattaché à",
            "LOCALISE_SUR": "est localisé sur",
            "COMPOSE_DE": "est composé de",
            "A_POUR_ORIGINE": "a pour origine",
            "A_POUR_DESTINATION": "a pour destination",
            "IMPACTE": "a un impact sur",
            "UTILISE": "utilise",
            "PROTEGE_PAR": "est protégé par",
            "DECRIT_PAR": "est décrit par",
            "EST_UN": "est un type de",
        }
        phrases = []
        for relation in relations[:8]:
            source = concepts.get(relation.get("source"), relation.get("source", ""))
            cible = concepts.get(relation.get("cible"), relation.get("cible", ""))
            verbe = formulations.get(
                relation.get("type"),
                str(relation.get("type", "est relié à")).lower().replace("_", " "),
            )
            phrases.append(f"le concept **{source}** {verbe} **{cible}**")
        return "Selon le graphe métier validé, " + "; ".join(phrases) + "."

    @staticmethod
    def _formater_structure_secours(question: str, sous_graphe: dict, racines: list[str]) -> str | None:
        """Répond aux demandes d'héritage UML sans dépendre du LLM."""
        q = question.lower()
        relations = sous_graphe.get("relations", [])
        if not racines:
            return "Je n’ai identifié aucune classe UML correspondant à la question."
        racines_set = set(racines)
        enfants = []
        for relation in relations:
            if relation.get("type") != "HERITE_DE" or relation.get("cible") not in racines_set:
                continue
            nom = relation.get("source")
            if nom and nom not in enfants:
                enfants.append(nom)
        racine = next(
            (r for r in racines if any(rel.get("cible") == r for rel in relations)),
            racines[0] if racines else "la classe demandée",
        )
        parents = []
        associations_type = []
        for relation in relations:
            if relation.get("source") not in racines_set:
                continue
            cible = relation.get("cible")
            if relation.get("type") == "HERITE_DE" and cible and cible not in parents:
                parents.append(cible)
            if (
                relation.get("type") == "ASSOCIE_A"
                and cible
                and str(cible).lower().startswith("type")
                and cible not in associations_type
            ):
                associations_type.append(cible)
        demande_types = any(mot in q for mot in ("type", "hérit", "herit", "enfant", "fille"))
        if demande_types and not enfants:
            reponse = (
                f"Dans le métamodèle UML, aucune classe du sous-graphe récupéré "
                f"n’hérite directement de **{racine}**."
            )
            if associations_type:
                reponse += (
                    f" En revanche, **{racine}** est associé à "
                    + ", ".join(f"**{nom}**" for nom in associations_type)
                    + " : il s’agit d’une association UML, pas d’une sous-classe."
                )
            if parents:
                reponse += " La classe hérite elle-même de " + ", ".join(
                    f"**{nom}**" for nom in parents
                ) + "."
            return reponse
        if not demande_types:
            details = []
            if parents:
                details.append("hérite de " + ", ".join(f"**{nom}**" for nom in parents))
            if associations_type:
                details.append("est associé à " + ", ".join(f"**{nom}**" for nom in associations_type))
            if details:
                return f"Dans le métamodèle UML, **{racine}** " + " et ".join(details) + "."
            return f"La classe UML **{racine}** a été trouvée, sans relation structurelle dans le sous-graphe récupéré."
        if len(enfants) == 1:
            enumeration = f"**{enfants[0]}**"
        else:
            enumeration = ", ".join(f"**{nom}**" for nom in enfants[:-1])
            enumeration += f" et **{enfants[-1]}**"
        return (
            f"Dans le métamodèle UML, les classes qui héritent directement de **{racine}** "
            f"sont {enumeration}. Elles représentent les spécialisations structurelles de "
            f"la classe **{racine}**, et non des relations du graphe métier."
        )

    @staticmethod
    def _formater_structure_uml(question: str, sous_graphe: dict, racines: list[str]) -> str:
        """Produit une réponse UML factuelle sans appel à un modèle de langage."""
        if not racines:
            return "Je n’ai identifié aucune classe UML correspondant exactement à la question."

        q = normaliser(question)
        racine = racines[0]
        attributs = [
            attribut for attribut in sous_graphe.get("attributs", [])
            if attribut.get("classe") == racine
        ]
        relations = [
            relation for relation in sous_graphe.get("relations", [])
            if relation.get("source") == racine or relation.get("cible") == racine
        ]

        def noms_types(attribut):
            valeurs = []
            type_attribut = attribut.get("type")
            if type_attribut and type_attribut not in valeurs:
                valeurs.append(type_attribut)
            return valeurs or ["type non renseigné"]

        # Une question structurelle peut cumuler plusieurs demandes. Les anciennes
        # branches retournaient dès qu'elles rencontraient « attribut », ce qui
        # masquait ensuite les relations et l'héritage demandés dans la même phrase.
        demande_attributs = "attribut" in q
        demande_relations = ("relation" in q and "direct" in q) or any(
            mot in q for mot in ("association", "composition", "agregation")
        )
        demande_parents = any(
            mot in q for mot in ("classe parente", "classes parentes", "parent", "herite de")
        )
        if sum((demande_attributs, demande_relations, demande_parents)) >= 2:
            sections = [f"## Classe UML `{racine}`"]

            if demande_attributs:
                regroupes = {}
                for attribut in attributs:
                    nom = attribut.get("attribut")
                    if not nom:
                        continue
                    regroupes.setdefault(nom, [])
                    for valeur in noms_types(attribut):
                        if valeur not in regroupes[nom]:
                            regroupes[nom].append(valeur)
                if regroupes:
                    lignes = [
                        f"- **{nom}** : " + ", ".join(f"`{valeur}`" for valeur in types)
                        for nom, types in regroupes.items()
                    ]
                    sections.append(
                        f"### Attributs directs ({len(regroupes)})\n\n" + "\n".join(lignes)
                    )
                else:
                    sections.append("### Attributs directs\n\nAucun attribut direct renseigné.")

            if demande_relations:
                # L'héritage est présenté dans la section dédiée lorsque les
                # classes parentes sont aussi demandées, afin d'éviter un doublon.
                selection = [
                    relation for relation in relations
                    if not (demande_parents and relation.get("type") == "HERITE_DE")
                ]
                if selection:
                    lignes = []
                    for relation in selection:
                        role = (relation.get("proprietes") or {}).get("role")
                        suffixe = f" (rôle : `{role}`)" if role else ""
                        lignes.append(
                            f"- **{relation.get('source')}** — `{relation.get('type')}` → "
                            f"**{relation.get('cible')}**{suffixe}"
                        )
                    sections.append(
                        f"### Relations UML directes hors héritage ({len(selection)})\n\n"
                        + "\n".join(lignes)
                    )
                else:
                    sections.append(
                        "### Relations UML directes hors héritage\n\nAucune relation directe trouvée."
                    )

            if demande_parents:
                parents = []
                for relation in relations:
                    if relation.get("source") != racine or relation.get("type") != "HERITE_DE":
                        continue
                    cible = relation.get("cible")
                    if cible and cible not in parents:
                        parents.append(cible)
                if parents:
                    sections.append(
                        "### Classes parentes\n\n"
                        + "\n".join(
                            f"- **{racine}** — `HERITE_DE` → **{parent}**" for parent in parents
                        )
                    )
                else:
                    sections.append(
                        "### Classes parentes\n\nAucune classe parente directe trouvée."
                    )

            return "\n\n".join(sections)

        if "attribut" in q and "type" in q:
            candidats = [
                attribut for attribut in attributs
                if normaliser(attribut.get("attribut", "")) in q
            ]
            if not candidats:
                return f"Aucun attribut demandé n’a été identifié dans la classe UML **{racine}**."
            nom = candidats[0].get("attribut")
            types = []
            for attribut in candidats:
                for valeur in noms_types(attribut):
                    if valeur not in types:
                        types.append(valeur)
            return (
                f"Dans le métamodèle UML, l’attribut **{nom}** de la classe "
                f"**{racine}** est relié "
                + ("au type " if len(types) == 1 else "aux types ")
                + ", ".join(f"`{valeur}`" for valeur in types)
                + "."
            )

        if "attribut" in q:
            if not attributs:
                return f"La classe UML **{racine}** ne possède aucun attribut direct renseigné."
            regroupes = {}
            for attribut in attributs:
                nom = attribut.get("attribut")
                regroupes.setdefault(nom, [])
                for valeur in noms_types(attribut):
                    if valeur not in regroupes[nom]:
                        regroupes[nom].append(valeur)
            lignes = [
                f"- **{nom}** : " + ", ".join(f"`{valeur}`" for valeur in types)
                for nom, types in regroupes.items()
            ]
            return (
                f"La classe UML **{racine}** possède {len(regroupes)} attribut"
                f"{'s' if len(regroupes) > 1 else ''} direct{'s' if len(regroupes) > 1 else ''} :\n\n"
                + "\n".join(lignes)
            )

        if any(mot in q for mot in ("herite", "heritent", "heritage", "types", "sousclasse", "enfant")):
            return AgentLG._formater_structure_secours(question, sous_graphe, racines)

        filtre = None
        if any(mot in q for mot in ("associe", "associee", "associees", "association")):
            filtre = "ASSOCIE_A"
        elif any(mot in q for mot in ("compose", "composent", "composition")):
            filtre = "COMPOSE_DE"

        if filtre:
            selection = [r for r in relations if r.get("type") == filtre]
            if filtre == "COMPOSE_DE" and "composent" in q:
                selection = [r for r in selection if r.get("source") == racine]
            if not selection:
                return f"Aucune relation `{filtre}` directe n’a été trouvée pour la classe **{racine}**."
            lignes = []
            for relation in selection:
                source, cible = relation.get("source"), relation.get("cible")
                role = (relation.get("proprietes") or {}).get("role")
                suffixe = f" (rôle : `{role}`)" if role else ""
                lignes.append(f"- **{source}** — `{filtre}` → **{cible}**{suffixe}")
            return (
                f"Dans le métamodèle UML, les relations `{filtre}` directes concernant "
                f"**{racine}** sont :\n\n" + "\n".join(lignes)
            )

        if "relation" in q and "direct" in q:
            if not relations:
                return f"Aucune relation UML directe n’a été trouvée pour **{racine}**."
            lignes = []
            for relation in relations:
                role = (relation.get("proprietes") or {}).get("role")
                suffixe = f" (rôle : `{role}`)" if role else ""
                lignes.append(
                    f"- **{relation.get('source')}** — `{relation.get('type')}` → "
                    f"**{relation.get('cible')}**{suffixe}"
                )
            return (
                f"La classe UML **{racine}** participe à {len(relations)} relation"
                f"{'s' if len(relations) > 1 else ''} directe{'s' if len(relations) > 1 else ''} :\n\n"
                + "\n".join(lignes)
            )

        classe = next(
            (item for item in sous_graphe.get("classes", []) if item.get("nom") == racine),
            {},
        )
        description = str(classe.get("description") or "").strip()
        debut = (
            f"Dans le métamodèle UML, **{racine}** est une classe."
            if not description else f"Dans le métamodèle UML, **{racine}** est définie ainsi : {description}"
        )
        return (
            f"{debut}\n\nElle possède {len({a.get('attribut') for a in attributs})} attribut(s) "
            f"direct(s) et participe à {len(relations)} relation(s) UML directe(s)."
        )

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
        provider: str = "mistral",
    ):
        debut = time.time()
        logger.info("Question reçue : %s", question)
        resultat_retrieval = None
        schema_reponse = None
        messages = None

        try:
            resultat_retrieval = self.retriever.retrieve(
                question,
                historique=historique,
            )
            schema_reponse = self._schema_depuis_retrieval(resultat_retrieval)
            if resultat_retrieval.get("mode") == "STRUCTURE":
                logger.info(
                    "Réponse UML déterministe : racines=%s classes=%s",
                    resultat_retrieval.get("classes_racines", []),
                    len(resultat_retrieval.get("sous_graphe", {}).get("classes", [])),
                )
                reponse = self._formater_structure_uml(
                    question,
                    resultat_retrieval.get("sous_graphe", {}),
                    resultat_retrieval.get("classes_racines", []),
                )
                return self._retour(reponse, schema_reponse, inclure_graphe)
            if resultat_retrieval.get("mode") == "CHEMIN_UML":
                chemin = resultat_retrieval.get("chemin_uml", {})
                if chemin.get("trouve") and len(chemin.get("candidats", [])) > 1:
                    try:
                        chemin = self._selectionner_chemin_uml_avec_llm(
                            question, chemin, provider
                        )
                        resultat_retrieval["chemin_uml"] = chemin
                        schema_reponse = self._schema_depuis_retrieval(resultat_retrieval)
                    except Exception as exc:
                        # Le premier candidat est déjà un résultat réel, orienté et
                        # scoré localement. Il constitue le secours déterministe.
                        logger.warning(
                            "Classement LLM des chemins UML indisponible ; "
                            "sélection déterministe conservée : %s",
                            exc,
                        )
                reponse = self._formater_chemin_uml(chemin)
                return self._retour(reponse, schema_reponse, inclure_graphe)
            if resultat_retrieval.get("mode") == "CHEMIN_METIER":
                chemin = resultat_retrieval.get("chemin_metier", {})
                reponse_controlee = self._formater_chemin_metier(chemin)
                if not chemin.get("trouve"):
                    return self._retour(reponse_controlee, None, inclure_graphe)
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Tu reformules un chemin Neo4j validé en français naturel. "
                            "Transforme chaque relation en une phrase grammaticalement correcte, "
                            "puis explique clairement le rôle du ou des concepts intermédiaires. "
                            "Donne entre deux et quatre phrases complètes afin que le raisonnement "
                            "du chemin soit compréhensible. Respecte exactement "
                            "le sens source, relation, cible. N'ajoute, ne supprime et ne déduis "
                            "aucune relation. N'affiche ni code, ni nom technique en majuscules, "
                            "ni source, ni tableau. Réponds directement en français naturel."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question : {question}\n\n"
                            f"Chemin contrôlé à reformuler :\n{reponse_controlee}"
                        ),
                    },
                ]
                texte = self._generer(provider, messages)
                return self._retour(texte, schema_reponse, inclure_graphe)
            logger.info(
                "Retrieval GraphRAG : mode=%s racines=%s classes=%s chunks=%s",
                resultat_retrieval["mode"],
                resultat_retrieval["classes_racines"],
                len(resultat_retrieval["sous_graphe"]["classes"]),
                len(resultat_retrieval["chunks"]),
            )
            contexte = self.retriever.contexte_pour_llm(resultat_retrieval)
            question_normalisee = question.lower().replace("é", "e").replace("è", "e")
            demande_sous_graphe_metier = "graphe metier" in question_normalisee
            if demande_sous_graphe_metier:
                # Les relations restent la seule autorité pour construire le graphe.
                # Les passages qui leur servent déjà de preuve sont néanmoins fournis
                # au LLM afin qu'il puisse expliquer leur sens métier en langage naturel.
                preuves_metier = [
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "texte": str(chunk.get("texte", ""))[:3000],
                    }
                    for chunk in resultat_retrieval.get("chunks", [])
                    if chunk.get("origine_retrieval") == "preuve_graphe_metier"
                ][:6]
                contexte = json.dumps(
                    {
                        "mode": "GRAPHE_METIER_CONTROLE",
                        "graphe_metier": resultat_retrieval.get("graphe_metier", {}),
                        "passages_justificatifs": preuves_metier,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Tu es l'assistant métier Arianes. Réponds uniquement à partir "
                        "du contexte GraphRAG fourni. Distingue clairement les faits du "
                        "métamodèle des extraits documentaires. "
                        "Réponds d'abord directement à la question dès la première phrase. "
                        "Fournis ensuite une explication développée avec les concepts concernés, "
                        "leurs relations, les conditions, les exceptions et les conséquences utiles "
                        "présentes dans le contexte. Adapte le niveau de détail à la question : pour "
                        "une demande simple, écris un à trois paragraphes substantiels ; pour une "
                        "demande contenant 'explique', 'décris', 'comment', 'pourquoi' ou 'détaille', "
                        "écris trois à six paragraphes structurés. Ne transforme toutefois pas une "
                        "question ciblée en rapport général et n'ajoute pas de contenu sans rapport. "
                        "N'utilise aucun tableau Markdown : présente les résultats sous forme de "
                        "paragraphes clairs ou de listes à puces lorsque plusieurs éléments sont à énumérer. "
                        "Ne répète pas la même information dans une synthèse. "
                        "Les relations de graphe_metier sont des connaissances issues des fiches, "
                        "pas des associations UML. Respecte leur champ condition et appuie tes "
                        "explications sur leurs preuves sans afficher les références techniques. "
                        "Une relation VALIDE est confirmée documentairement mais pas nécessairement "
                        "certifiée par un expert. Présente une relation PROBABLE avec une formulation "
                        "prudente comme 'selon la fiche', 'peut' ou 'semble', en expliquant sa condition, "
                        "son exception ou son avertissement. Ne présente jamais PROBABLE comme une règle universelle. "
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
                        "question structurelle, privilégie les classes, attributs et relations. "
                        "Dans une question comme 'quels sont les types de X', interprète 'types' "
                        "comme les classes qui héritent de la classe UML X, sauf si l'utilisateur "
                        "demande explicitement des catégories documentaires ou métier. "
                        "Réponds en français, de manière claire, précise et suffisamment détaillée."
                        + (
                            " La demande porte sur un graphe métier contrôlé. Le schéma affiché par "
                            "l'interface est seulement un complément visuel : ta réponse textuelle "
                            "doit rester autonome et détaillée. Commence par deux ou trois phrases "
                            "qui définissent le concept central et son rôle. Explique ensuite chaque "
                            "relation présente dans graphe_metier.relations par une phrase complète "
                            "et grammaticalement correcte, une seule fois et dans son sens source "
                            "vers cible. Pour chaque relation, précise son sens métier ainsi que sa "
                            "condition ou son exception lorsqu'elle est fournie. Utilise "
                            "passages_justificatifs pour enrichir l'explication, mais jamais pour "
                            "créer une relation absente de graphe_metier.relations. Termine par une "
                            "courte explication de la manière dont ces relations s'articulent, sans "
                            "répéter leur simple liste. Une description de concept n'est jamais une "
                            "relation. N'invente aucun héritage, aucune manœuvre ni aucun rattachement "
                            "absent de la liste relations."
                            if demande_sous_graphe_metier else ""
                        )
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
            texte = self._generer(provider, messages)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.error("Connexion au service Mistral impossible : %s", exc)
            return (
                f"Le graphe Neo4j est disponible, mais le fournisseur {provider} "
                "est inaccessible. Vérifie la connexion réseau ou le proxy."
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Erreur HTTP du fournisseur %s (%s) : %s",
                provider,
                exc.response.status_code,
                exc,
            )
            if exc.response.status_code == 429 or exc.response.status_code >= 500:
                return (
                    f"Le fournisseur {provider} est temporairement indisponible ou a atteint "
                    "sa limite. Sélectionne un autre fournisseur ou réessaie plus tard."
                )
            return (
                f"Le fournisseur {provider} a refusé la requête. "
                "Vérifie sa clé API et sa configuration."
            )
        except RuntimeError as exc:
            logger.error("Fournisseur %s indisponible : %s", provider, exc)
            return f"Le fournisseur {provider} est indisponible : {exc}"
        except Exception:
            logger.exception("Erreur inattendue lors de l'appel agent")
            return (
                "Une erreur inattendue empêche l'agent de répondre. "
                "Consulte les journaux du serveur."
            )

        logger.info("Temps total : %.2fs", time.time() - debut)
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
