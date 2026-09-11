"""
Application complète Ariane Cœur — API + interface web, en UN SEUL fichier/processus.

Le graphe métier (Classe, Document, Chunk...) reste dans Neo4j (via AgentLG).
L'historique des conversations est stocké dans SQLite (fichier local, aucune
installation ni droits admin nécessaires) via SQLModel.

Migration future vers PostgreSQL (dès que l'accès sera fourni) : changer
uniquement DATABASE_URL, aucune requête à réécrire.

Lancement (une seule commande, depuis ce dossier) :
    python -m uvicorn api:app --reload

Puis ouvre simplement : http://127.0.0.1:8000
"""

import os
import json
import uuid
import hashlib
import hmac
import secrets
import logging
from threading import Lock
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import inspect, text
from dotenv import load_dotenv

from arianes.agent import AgentLG

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ariane_coeur.db")

# check_same_thread=False : necessaire car FastAPI traite les requetes
# potentiellement sur des threads differents ; sans risque ici car chaque
# fonction ouvre/ferme sa propre Session.
engine = create_engine(DATABASE_URL, connect_args=(
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite:") else {}
))

# Sérialisation pour le déploiement local mono-processus (pas multi-workers).
_conversation_locks = [Lock() for _ in range(64)]

agent: AgentLG | None = None


# ------------------------------------------------------------------
# Modeles de donnees (equivalent des entites JPA : une seule classe
# sert a la fois de table SQL et de schema de validation Pydantic)
# ------------------------------------------------------------------
class Conversation(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    titre: str
    date_creation: datetime = Field(default_factory=datetime.now)


class Message(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversation.id")
    role: str
    contenu: str
    position: int
    provider: str | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)


class VisualisationMessage(SQLModel, table=True):
    message_id: uuid.UUID = Field(foreign_key="message.id", primary_key=True)
    graphe_json: str


class Utilisateur(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nom_utilisateur: str = Field(unique=True, index=True)
    sel_mot_de_passe: str
    hash_mot_de_passe: str
    date_creation: datetime = Field(default_factory=datetime.now)


class SessionAuthentification(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    utilisateur_id: uuid.UUID = Field(foreign_key="utilisateur.id", index=True)
    hash_jeton: str = Field(unique=True, index=True)
    expiration: datetime


class ProprietaireConversation(SQLModel, table=True):
    conversation_id: uuid.UUID = Field(foreign_key="conversation.id", primary_key=True)
    utilisateur_id: uuid.UUID = Field(foreign_key="utilisateur.id", index=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    print("Initialisation de l'agent Ariane Coeur...")
    agent = AgentLG()
    print("Initialisation du schema SQLite (historique des conversations)...")
    SQLModel.metadata.create_all(engine)
    if "provider" not in {colonne["name"] for colonne in inspect(engine).get_columns("message")}:
        with engine.begin() as connexion:
            connexion.execute(text("ALTER TABLE message ADD COLUMN provider VARCHAR"))
    yield
    print("Fermeture de la connexion Neo4j...")
    agent.driver.close()


app = FastAPI(title="Ariane Cœur", lifespan=lifespan)


# --- Schemas API (entree/sortie) ---
class Question(BaseModel):
    question: str
    conversation_id: str | None = None
    provider: Literal["mistral", "gemini", "groq"] = "gemini"


class Reponse(BaseModel):
    question: str
    reponse: str
    conversation_id: str
    provider: str
    graphe: dict | None = None


class ConversationResume(BaseModel):
    id: str
    titre: str
    date_creation: str


class MessageItem(BaseModel):
    role: str
    contenu: str
    provider: str | None = None
    graphe: dict | None = None


class Identifiants(BaseModel):
    nom_utilisateur: str
    mot_de_passe: str


class UtilisateurPublic(BaseModel):
    id: str
    nom_utilisateur: str


# ------------------------------------------------------------------
# Persistance des conversations (SQLModel remplace le SQL brut)
# ------------------------------------------------------------------
SESSION_COOKIE = "ariane_session"
SESSION_DURATION = timedelta(days=7)


def _normaliser_nom(nom: str) -> str:
    nom = nom.strip().lower()
    if len(nom) < 3 or len(nom) > 50:
        raise HTTPException(status_code=400, detail="Le nom d'utilisateur doit contenir entre 3 et 50 caractères.")
    if not all(c.isalnum() or c in "._-" for c in nom):
        raise HTTPException(status_code=400, detail="Le nom d'utilisateur contient des caractères non autorisés.")
    return nom


def _valider_mot_de_passe(mot_de_passe: str):
    if len(mot_de_passe) < 10:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 10 caractères.")
    if len(mot_de_passe) > 200:
        raise HTTPException(status_code=400, detail="Le mot de passe est trop long.")


def _hash_mot_de_passe(mot_de_passe: str, sel: bytes | None = None) -> tuple[str, str]:
    sel = sel or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, 600_000)
    return sel.hex(), digest.hex()


def _verifier_mot_de_passe(mot_de_passe: str, sel_hex: str, hash_attendu: str) -> bool:
    _, calcule = _hash_mot_de_passe(mot_de_passe, bytes.fromhex(sel_hex))
    return hmac.compare_digest(calcule, hash_attendu)


def _hash_jeton(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def _creer_session(session: Session, utilisateur_id: uuid.UUID) -> str:
    jeton = secrets.token_urlsafe(32)
    session.add(SessionAuthentification(
        utilisateur_id=utilisateur_id,
        hash_jeton=_hash_jeton(jeton),
        expiration=datetime.now() + SESSION_DURATION,
    ))
    session.commit()
    return jeton


def _definir_cookie_session(response: Response, jeton: str):
    response.set_cookie(
        key=SESSION_COOKIE,
        value=jeton,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )


def _utilisateur_courant(request: Request) -> Utilisateur:
    jeton = request.cookies.get(SESSION_COOKIE)
    if not jeton:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    with Session(engine) as session:
        auth = session.exec(
            select(SessionAuthentification).where(
                SessionAuthentification.hash_jeton == _hash_jeton(jeton)
            )
        ).first()
        if auth is None or auth.expiration <= datetime.now():
            if auth is not None:
                session.delete(auth)
                session.commit()
            raise HTTPException(status_code=401, detail="Session expirée ou invalide.")
        utilisateur = session.get(Utilisateur, auth.utilisateur_id)
        if utilisateur is None:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable.")
        session.expunge(utilisateur)
        return utilisateur


def _verifier_proprietaire(session: Session, conversation_id: uuid.UUID, utilisateur_id: uuid.UUID):
    lien = session.get(ProprietaireConversation, conversation_id)
    if lien is None or lien.utilisateur_id != utilisateur_id:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")


def _creer_conversation(titre: str, utilisateur_id: uuid.UUID) -> str:
    with Session(engine) as session:
        conv = Conversation(titre=titre[:60])
        session.add(conv)
        session.commit()
        session.refresh(conv)
        session.add(ProprietaireConversation(conversation_id=conv.id, utilisateur_id=utilisateur_id))
        session.commit()
        return str(conv.id)


def _prochaine_position(conversation_id: str) -> int:
    with Session(engine) as session:
        statement = select(Message).where(Message.conversation_id == uuid.UUID(conversation_id))
        return len(session.exec(statement).all())


def _uuid_valide(conversation_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(conversation_id)
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Identifiant de conversation invalide.")


def _charger_historique(conversation_id: str, utilisateur_id: uuid.UUID) -> list[dict[str, str]]:
    conv_id = _uuid_valide(conversation_id)
    with Session(engine) as session:
        _verifier_proprietaire(session, conv_id, utilisateur_id)
        if session.get(Conversation, conv_id) is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable.")
        statement = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.position)
        )
        messages = session.exec(statement).all()
    roles = {"utilisateur": "user", "assistant": "assistant"}
    return [
        {"role": roles[m.role], "content": m.contenu}
        for m in messages
        if m.role in roles
    ]


def _enregistrer_message(
    conversation_id: str,
    role: str,
    contenu: str,
    position: int,
    provider: str | None = None,
) -> uuid.UUID:
    with Session(engine) as session:
        msg = Message(
            conversation_id=uuid.UUID(conversation_id),
            role=role,
            contenu=contenu,
            position=position,
            provider=provider,
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        return msg.id


def _enregistrer_graphe(message_id: uuid.UUID, graphe: dict | None):
    if not graphe:
        return
    with Session(engine) as session:
        session.add(VisualisationMessage(
            message_id=message_id,
            graphe_json=json.dumps(graphe, ensure_ascii=False),
        ))
        session.commit()



@app.post("/auth/register", response_model=UtilisateurPublic, status_code=201)
def register(payload: Identifiants, response: Response):
    nom = _normaliser_nom(payload.nom_utilisateur)
    _valider_mot_de_passe(payload.mot_de_passe)
    sel, password_hash = _hash_mot_de_passe(payload.mot_de_passe)
    with Session(engine) as session:
        if session.exec(select(Utilisateur).where(Utilisateur.nom_utilisateur == nom)).first():
            raise HTTPException(status_code=409, detail="Ce nom d'utilisateur existe déjà.")
        utilisateur = Utilisateur(nom_utilisateur=nom, sel_mot_de_passe=sel, hash_mot_de_passe=password_hash)
        session.add(utilisateur)
        session.commit()
        session.refresh(utilisateur)
        utilisateur_public = UtilisateurPublic(
            id=str(utilisateur.id), nom_utilisateur=utilisateur.nom_utilisateur
        )
        jeton = _creer_session(session, utilisateur.id)
    _definir_cookie_session(response, jeton)
    return utilisateur_public


@app.post("/auth/login", response_model=UtilisateurPublic)
def login(payload: Identifiants, response: Response):
    nom = _normaliser_nom(payload.nom_utilisateur)
    with Session(engine) as session:
        utilisateur = session.exec(select(Utilisateur).where(Utilisateur.nom_utilisateur == nom)).first()
        if utilisateur is None or not _verifier_mot_de_passe(
            payload.mot_de_passe, utilisateur.sel_mot_de_passe, utilisateur.hash_mot_de_passe
        ):
            raise HTTPException(status_code=401, detail="Nom d'utilisateur ou mot de passe incorrect.")
        utilisateur_public = UtilisateurPublic(
            id=str(utilisateur.id), nom_utilisateur=utilisateur.nom_utilisateur
        )
        jeton = _creer_session(session, utilisateur.id)
    _definir_cookie_session(response, jeton)
    return utilisateur_public


@app.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    jeton = request.cookies.get(SESSION_COOKIE)
    if jeton:
        with Session(engine) as session:
            auth = session.exec(select(SessionAuthentification).where(
                SessionAuthentification.hash_jeton == _hash_jeton(jeton)
            )).first()
            if auth:
                session.delete(auth)
                session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@app.get("/auth/me", response_model=UtilisateurPublic)
def me(request: Request):
    utilisateur = _utilisateur_courant(request)
    return UtilisateurPublic(id=str(utilisateur.id), nom_utilisateur=utilisateur.nom_utilisateur)


@app.post("/ask", response_model=Reponse)
def ask(payload: Question, request: Request):
    utilisateur = _utilisateur_courant(request)
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")
    if len(question) > 4000:
        raise HTTPException(status_code=400, detail="La question est trop longue (maximum 4000 caractères).")

    conversation_id = payload.conversation_id
    if not conversation_id:
        conversation_id = _creer_conversation(titre=question, utilisateur_id=utilisateur.id)

    verrou = _conversation_locks[hash(conversation_id) % len(_conversation_locks)]
    if not verrou.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Une réponse est déjà en cours. Réessaie après sa fin.")
    try:
        historique = _charger_historique(conversation_id, utilisateur.id)
        position = _prochaine_position(conversation_id)
        _enregistrer_message(
            conversation_id, "utilisateur", question, position, payload.provider
        )

        resultat_agent = agent.ask(
            question,
            historique=historique,
            inclure_graphe=True,
            provider=payload.provider,
        )
        if isinstance(resultat_agent, dict):
            reponse = resultat_agent["reponse"]
            graphe = resultat_agent.get("graphe")
        else:
            reponse = resultat_agent
            graphe = None

        message_id = _enregistrer_message(
            conversation_id, "assistant", reponse, position + 1, payload.provider
        )
        _enregistrer_graphe(message_id, graphe)

        return Reponse(
            question=question, reponse=reponse,
            conversation_id=conversation_id, provider=payload.provider, graphe=graphe,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Échec de traitement de la conversation")
        raise HTTPException(status_code=500, detail="Erreur lors du traitement. Consulte les journaux du serveur.") from e
    finally:
        verrou.release()


@app.get("/conversations", response_model=list[ConversationResume])
def lister_conversations(request: Request):
    utilisateur = _utilisateur_courant(request)
    with Session(engine) as session:
        statement = (
            select(Conversation)
            .join(ProprietaireConversation, ProprietaireConversation.conversation_id == Conversation.id)
            .where(ProprietaireConversation.utilisateur_id == utilisateur.id)
            .order_by(Conversation.date_creation.desc())
        )
        conversations = session.exec(statement).all()
    return [
        {"id": str(c.id), "titre": c.titre, "date_creation": c.date_creation.isoformat()}
        for c in conversations
    ]


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageItem])
def charger_messages(conversation_id: str, request: Request):
    utilisateur = _utilisateur_courant(request)
    conv_id = _uuid_valide(conversation_id)
    with Session(engine) as session:
        _verifier_proprietaire(session, conv_id, utilisateur.id)
        statement = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.position)
        )
        messages = session.exec(statement).all()
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    resultat = []
    with Session(engine) as session:
        for message in messages:
            visualisation = session.get(VisualisationMessage, message.id)
            graphe = json.loads(visualisation.graphe_json) if visualisation else None
            resultat.append({
                "role": message.role,
                "contenu": message.contenu,
                "provider": message.provider,
                "graphe": graphe,
            })
    return resultat


@app.get("/providers")
def lister_fournisseurs(request: Request):
    _utilisateur_courant(request)
    return {
        "default": "gemini",
        "providers": [
            {"id": identifiant, "configured": configure}
            for identifiant, configure in agent.fournisseurs_disponibles().items()
        ],
    }


@app.delete("/conversations/{conversation_id}")
def supprimer_conversation(conversation_id: str, request: Request):
    utilisateur = _utilisateur_courant(request)
    conv_id = _uuid_valide(conversation_id)
    with Session(engine) as session:
        _verifier_proprietaire(session, conv_id, utilisateur.id)
        conv = session.get(Conversation, conv_id)
        if conv:
            # Suppression manuelle des messages lies (pas de CASCADE automatique
            # aussi simple qu'en SQL brut avec SQLite/SQLModel par defaut)
            statement = select(Message).where(Message.conversation_id == conv_id)
            for msg in session.exec(statement).all():
                visualisation = session.get(VisualisationMessage, msg.id)
                if visualisation:
                    session.delete(visualisation)
                session.delete(msg)
            lien = session.get(ProprietaireConversation, conv_id)
            if lien:
                session.delete(lien)
            session.delete(conv)
            session.commit()
    return {"ok": True}


@app.get("/schema")
def schema(request: Request):
    _utilisateur_courant(request)
    try:
        return {"schema": agent.get_schema_context()}
    except Exception:
        raise HTTPException(status_code=503, detail="Neo4j est indisponible.")


@app.get("/graph")
def graphe_visible(request: Request, vue: str = "metier"):
    """Retourne un aperçu borné et en lecture seule pour la visualisation web."""
    _utilisateur_courant(request)
    requetes = {
        "metier": """
            MATCH (a:ConceptMetier)-[r:RELATION_METIER]->(b:ConceptMetier)
            WHERE coalesce(a.actif, a.valide, false) AND coalesce(b.actif, b.valide, false)
              AND coalesce(r.actif, r.valide, false)
              AND coalesce(r.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
              AND coalesce(a.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
              AND coalesce(b.statut, 'PROBABLE') IN ['VALIDE', 'PROBABLE']
            RETURN elementId(a) AS source_id, a.nom AS source_nom,
                   'Concept métier' AS source_categorie,
                   coalesce(a.description, '') AS source_description,
                   elementId(b) AS cible_id, b.nom AS cible_nom,
                   'Concept métier' AS cible_categorie,
                   coalesce(b.description, '') AS cible_description,
                   coalesce(r.type, type(r)) AS relation
            ORDER BY source_nom, relation, cible_nom LIMIT 160
        """,
        "metamodele": """
            MATCH (a:Classe)-[r]->(b:Classe)
            WHERE type(r) IN ['HERITE_DE', 'COMPOSE_DE', 'ASSOCIE_A', 'AGREGE']
            RETURN elementId(a) AS source_id, a.nom AS source_nom,
                   'Classe' AS source_categorie,
                   coalesce(a.description, '') AS source_description,
                   elementId(b) AS cible_id, b.nom AS cible_nom,
                   'Classe' AS cible_categorie,
                   coalesce(b.description, '') AS cible_description,
                   type(r) AS relation
            ORDER BY source_nom, relation, cible_nom LIMIT 160
        """,
    }
    if vue not in requetes:
        raise HTTPException(status_code=400, detail="Vue de graphe inconnue.")
    try:
        with agent.driver.session() as session:
            relations = [record.data() for record in session.run(requetes[vue])]
    except Exception:
        raise HTTPException(status_code=503, detail="Neo4j est indisponible.")

    noeuds = {}
    liens = []
    for relation in relations:
        noeuds[relation["source_id"]] = {
            "id": relation["source_id"], "label": relation["source_nom"],
            "categorie": relation["source_categorie"],
            "description": relation["source_description"],
        }
        noeuds[relation["cible_id"]] = {
            "id": relation["cible_id"], "label": relation["cible_nom"],
            "categorie": relation["cible_categorie"],
            "description": relation["cible_description"],
        }
        liens.append({
            "source": relation["source_id"], "cible": relation["cible_id"],
            "label": relation["relation"],
        })
    return {"vue": vue, "nodes": list(noeuds.values()), "links": liens}


@app.get("/health")
def health():
    try:
        agent.driver.verify_connectivity()
    except Exception:
        raise HTTPException(status_code=503, detail="API disponible, mais Neo4j est indisponible.")
    return {"status": "ok", "neo4j": "connected"}



@app.get("/")
def accueil():
    return FileResponse(str(Path(__file__).resolve().parent / "index.html"))
