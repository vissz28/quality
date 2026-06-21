from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GitLab
    GITLAB_URL: str = "https://gitlab.com"
    GITLAB_USERNAME: str = ""              # Account the GITLAB_TOKEN belongs to
    GITLAB_TOKEN: str                      # Personal or project access token
    GITLAB_WEBHOOK_SECRET: str             # Set the same value in GitLab webhook config

    # Anthropic
    ANTHROPIC_API_KEY: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
