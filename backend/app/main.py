import asyncio
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.v1.endpoints import users, login, workouts
from .database import engine
from . import models


# Adiciona uma correção para um problema comum do asyncio no Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código a ser executado durante a inicialização
    print("Iniciando a aplicação...")
    models.Base.metadata.create_all(bind=engine)
    yield
    # Código a ser executado durante o desligamento (se necessário)
    print("Aplicação encerrada.")


# Cria uma instância da aplicação FastAPI com o gerenciador de lifespan
app = FastAPI(
    title="EvoRun API",
    description="A API central para o aplicativo de fitness gamificado EvoRun.",
    version="0.1.0",
    lifespan=lifespan
)

# Inclui os roteadores
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(login.router, prefix="/api/v1/login", tags=["login"])
app.include_router(workouts.router, prefix="/api/v1/workouts", tags=["workouts"])
# Todas as rotas em 'users.router', por exemplo, serão prefixadas com '/api/v1/users'

# Define um endpoint para a rota raiz ("/")
@app.get("/")
def read_root():
    """
    Endpoint de boas-vindas da API.
    """
    return {"message": "Olá, Mundo! Bem-vindo à API do EvoRun."}
