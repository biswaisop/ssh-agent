from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    GROQ: str
    SSH_HOST: str = "54.206.74.122"
    SSH_PORT: int = 22
    SSH_USERNAME: str = "ubuntu"
    KEY_PATH: str = "C:/Users/monda/.ssh/id_rsa"
    PASSWORD: Optional[str] = None
    
    MODEL: str = "llama-3.3-70b-versatile"
    TEMPERATURE: int = 0
    MAX_STDOUT_CHARS: int = 3000

    model_config = {
        "env_file": ".env",
        "env_prefix": "",
        "extra": "ignore"
    }

settings = Settings()
