from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

from mini_agent_neo4j_mistral import GraphAgent  # ton fichier existant


agent: GraphAgent | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = GraphAgent()
    yield
    agent.close()

app = FastAPI(title="Agent Ariane - GraphRAG API", lifespan=lifespan)


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    question: str
    cypher: str
    answer: str


@app.post("/ask", response_model=AnswerResponse)
def ask(request: QuestionRequest):
    try:
        cypher = agent.generate_cypher(request.question)
        results = agent.execute_cypher(cypher)
        answer = agent.answer_from_results(request.question, cypher, results)
        return AnswerResponse(question=request.question, cypher=cypher, answer=answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")


@app.get("/health")
def health():
    return {"status": "ok"}