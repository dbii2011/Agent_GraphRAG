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
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select
from dotenv import load_dotenv

from Agent_LG import AgentLG  # ta classe existante, inchangée

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ariane_coeur.db")

# check_same_thread=False : necessaire car FastAPI traite les requetes
# potentiellement sur des threads differents ; sans risque ici car chaque
# fonction ouvre/ferme sa propre Session.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

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
    timestamp: datetime = Field(default_factory=datetime.now)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    print("Initialisation de l'agent Ariane Coeur...")
    agent = AgentLG()
    print("Initialisation du schema SQLite (historique des conversations)...")
    SQLModel.metadata.create_all(engine)
    yield
    print("Fermeture de la connexion Neo4j...")
    agent.driver.close()


app = FastAPI(title="Ariane Cœur", lifespan=lifespan)


# --- Schemas API (entree/sortie) ---
class Question(BaseModel):
    question: str
    conversation_id: str | None = None


class Reponse(BaseModel):
    question: str
    reponse: str
    conversation_id: str


class ConversationResume(BaseModel):
    id: str
    titre: str
    date_creation: str


class MessageItem(BaseModel):
    role: str
    contenu: str


# ------------------------------------------------------------------
# Persistance des conversations (SQLModel remplace le SQL brut)
# ------------------------------------------------------------------
def _creer_conversation(titre: str) -> str:
    with Session(engine) as session:
        conv = Conversation(titre=titre[:60])
        session.add(conv)
        session.commit()
        session.refresh(conv)
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


def _charger_historique(conversation_id: str) -> list[dict[str, str]]:
    conv_id = _uuid_valide(conversation_id)
    with Session(engine) as session:
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


def _enregistrer_message(conversation_id: str, role: str, contenu: str, position: int):
    with Session(engine) as session:
        msg = Message(
            conversation_id=uuid.UUID(conversation_id),
            role=role,
            contenu=contenu,
            position=position,
        )
        session.add(msg)
        session.commit()



@app.post("/ask", response_model=Reponse)
def ask(payload: Question):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")
    if len(question) > 4000:
        raise HTTPException(status_code=400, detail="La question est trop longue (maximum 4000 caractères).")

    conversation_id = payload.conversation_id
    if not conversation_id:
        conversation_id = _creer_conversation(titre=question)

    try:
        historique = _charger_historique(conversation_id)
        position = _prochaine_position(conversation_id)
        _enregistrer_message(conversation_id, "utilisateur", question, position)

        reponse = agent.ask(question, historique=historique)

        _enregistrer_message(conversation_id, "assistant", reponse, position + 1)

        return Reponse(question=question, reponse=reponse, conversation_id=conversation_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement : {str(e)}")


@app.get("/conversations", response_model=list[ConversationResume])
def lister_conversations():
    with Session(engine) as session:
        statement = select(Conversation).order_by(Conversation.date_creation.desc())
        conversations = session.exec(statement).all()
    return [
        {"id": str(c.id), "titre": c.titre, "date_creation": c.date_creation.isoformat()}
        for c in conversations
    ]


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageItem])
def charger_messages(conversation_id: str):
    conv_id = _uuid_valide(conversation_id)
    with Session(engine) as session:
        statement = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.position)
        )
        messages = session.exec(statement).all()
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return [{"role": m.role, "contenu": m.contenu} for m in messages]


@app.delete("/conversations/{conversation_id}")
def supprimer_conversation(conversation_id: str):
    conv_id = _uuid_valide(conversation_id)
    with Session(engine) as session:
        conv = session.get(Conversation, conv_id)
        if conv:
            # Suppression manuelle des messages lies (pas de CASCADE automatique
            # aussi simple qu'en SQL brut avec SQLite/SQLModel par defaut)
            statement = select(Message).where(Message.conversation_id == conv_id)
            for msg in session.exec(statement).all():
                session.delete(msg)
            session.delete(conv)
            session.commit()
    return {"ok": True}


@app.get("/schema")
def schema():
    return {"schema": agent.get_schema_context()}



@app.get("/")
def accueil():
    return FileResponse("index.html")
