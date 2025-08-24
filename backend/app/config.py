from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Chave secreta para assinar os JWTs.
    # IMPORTANTE: Em produção, isso DEVE vir de uma variável de ambiente
    # e ser uma string longa e aleatória.
    # Você pode gerar uma com: openssl rand -hex 32
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

# Cria uma instância das configurações que será usada na aplicação
settings = Settings()
