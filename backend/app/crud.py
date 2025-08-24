from sqlalchemy.orm import Session
from . import models, schemas
from .security import get_password_hash
from .security import verify_password

# --- Funções de Autenticação (Auth) ---

def authenticate_user(db: Session, email: str, password: str):
    """
    Verifica se um usuário existe e se a senha está correta.
    """
    user = get_user_by_email(db, email=email)
    if not user:
        return None # Usuário não encontrado
    if not verify_password(password, user.hashed_password):
        return None # Senha incorreta
    return user

# --- Funções de Leitura (Read) ---

def get_user(db: Session, user_id: int):
    """
    Busca um único usuário pelo seu ID.
    - db: A sessão do banco de dados.
    - user_id: O ID do usuário a ser buscado.
    """
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    """
    Busca um único usuário pelo seu e-mail.
    - db: A sessão do banco de dados.
    - email: O e-mail do usuário a ser buscado.
    """
    return db.query(models.User).filter(models.User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    """
    Busca uma lista de usuários com paginação.
    - db: A sessão do banco de dados.
    - skip: O número de registros a pular.
    - limit: O número máximo de registros a retornar.
    """
    return db.query(models.User).offset(skip).limit(limit).all()


# --- Funções de Criação (Create) ---

def create_user(db: Session, user: schemas.UserCreate):
    """
    Cria um novo usuário no banco de dados com senha hasheada.
    - db: A sessão do banco de dados.
    - user: Um objeto schema UserCreate com os dados do novo usuário.
    """

    # Gera o hash da senha recebida no schema
    hashed_password = get_password_hash(user.password)
    
    # Cria a instância do modelo com a senha hasheada
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password
    )
    
    # Adiciona a nova instância à sessão do banco de dados
    db.add(db_user)
    # Confirma (persiste) as mudanças no banco
    db.commit()
    # Atualiza a instância db_user com os dados do banco (como o ID gerado)
    db.refresh(db_user)
    
    return db_user


# --- Funções de Atualização (Update) ---

def update_user(db: Session, db_user: models.User, user_in: schemas.UserUpdate):
    """
    Atualiza um usuário no banco de dados.
    - db: A sessão do banco de dados.
    - db_user: O objeto do usuário a ser atualizado (obtido do banco).
    - user_in: O schema com os dados a serem atualizados.
    """
    # Converte o schema Pydantic para um dicionário, excluindo campos não definidos
    update_data = user_in.model_dump(exclude_unset=True)

    # Se a senha estiver sendo atualizada, faz o hash da nova senha
    if "password" in update_data:
        hashed_password = get_password_hash(update_data["password"])
        update_data["hashed_password"] = hashed_password
        del update_data["password"] # Remove a senha em texto puro

    # Itera sobre os dados a serem atualizados e os aplica ao objeto do usuário
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# --- Funções de Remoção (Delete) ---

def delete_user(db: Session, user_id: int):
    """
    Deleta um usuário do banco de dados.
    - db: A sessão do banco de dados.
    - user_id: O ID do usuário a ser deletado.
    """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user

# --- Funções CRUD para Workouts ---

def create_user_workout(db: Session, workout: schemas.WorkoutCreate, user_id: int):
    """
    Cria um novo treino para um usuário específico.
    """
    db_workout = models.Workout(**workout.model_dump(), owner_id=user_id)
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return db_workout

def get_workouts_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """
    Busca todos os treinos de um usuário específico com paginação.
    """
    return db.query(models.Workout).filter(models.Workout.owner_id == user_id).offset(skip).limit(limit).all()