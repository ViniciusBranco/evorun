from enum import Enum

class WorkoutType(str, Enum):
    """
    Define os tipos de treino suportados pela aplicação.
    """
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    WEIGHTLIFTING = "weightlifting"