from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from passlib.context import CryptContext

from config import settings

# Cria um contexto para o hashing de senhas.
# - schemes=["bcrypt"]: Especifica que o bcrypt é o algoritmo de hashing padrão.
# - deprecated="auto": Marca automaticamente hashes antigos como depreciados se
#   novos algoritmos ou configurações forem adicionados no futuro.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto puro corresponde a uma senha com hash.

    - plain_password: A senha digitada pelo usuário.
    - hashed_password: A senha com hash salva no banco de dados.
    - Retorna True se as senhas corresponderem, False caso contrário.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera o hash de uma senha em texto puro.

    - password: A senha a ser hasheada.
    - Retorna a string do hash da senha.
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Cria um novo token de acesso (JWT).
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Usa o tempo de expiração padrão das configurações
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Gera o token JWT
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
