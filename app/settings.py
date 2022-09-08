from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    TODO: Application settings ...
    """

    debug: bool = False
    celery_broker: str = "redis://redis:6379/0"
    frequency: int = 1  # default monitoring frequency
    database_url: str = "postgresql://admin:quest@questdb:8812/qdb"
    database_pool_size: int = 3
    website_url: str

    class Config:
        """
        Meta configuration of the settings parser.
        """

        # Prefix the environment variable not to mix up with other variables
        # used by the OS or other software.
        env_prefix = "statuspage_"


settings = Settings()
