from enum import Enum

class _CaseInsensitiveEnum(Enum):
    """
    Uma classe Enum base que permite a correspondência de valores sem diferenciar maiúsculas de minúsculas.
    """
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None

class WorkoutType(str, _CaseInsensitiveEnum):
    """
    Define os tipos de treino suportados.
    Agora é insensível a maiúsculas/minúsculas ao ser validado.
    """
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    WEIGHTLIFTING = "weightlifting"
    STAIRS = "stairs"

