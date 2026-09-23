from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TRUTHY_VALUES = {"1", "true", "yes", "sim", "on"}


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: str = Field("sqlite:///./ecg_review.db", alias="DATABASE_URL")
    reset_on_startup: bool = Field(False, alias="RESET_DATABASE_ON_STARTUP")
    run_migrations_on_startup: bool = Field(False, alias="RUN_MIGRATIONS_ON_STARTUP")

    @field_validator("reset_on_startup", "run_migrations_on_startup", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in TRUTHY_VALUES
        return value

    @property
    def connect_args(self) -> dict:
        return {"check_same_thread": False} if self.url.startswith("sqlite") else {}


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = Field("dev-only-change-this-secret-key", alias="AUTH_SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(480, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    default_user_username: str = Field("dr.joao", alias="DEFAULT_USER_USERNAME")
    default_user_password: str | None = Field(None, alias="DEFAULT_USER_PASSWORD")
    default_user_full_name: str = Field("Dr. João", alias="DEFAULT_USER_FULL_NAME")
    default_admin_username: str = Field("admin", alias="DEFAULT_ADMIN_USERNAME")
    default_admin_password: str | None = Field(None, alias="DEFAULT_ADMIN_PASSWORD")
    default_admin_full_name: str = Field("Administrador Operacional", alias="DEFAULT_ADMIN_FULL_NAME")
    allowed_email_domains: str | None = Field(None, alias="BP_ALLOWED_EMAIL_DOMAINS")


class MetadataSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_path: str | None = Field(None, alias="METADATA_DATABASE_PATH")


class ValidationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    cycle_day: str | None = Field(None, alias="VALIDATION_CYCLE_DAY")
    active_diagnosis: str | None = Field(None, alias="VALIDATION_ACTIVE_DIAGNOSIS")
    ai_mode_enabled: str | None = Field(None, alias="AI_MODE_ENABLED")


class SupportSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    label: str | None = Field(None, alias="SUPPORT_CONTACT_LABEL")
    type: str = Field("text", alias="SUPPORT_CONTACT_TYPE")
    value: str | None = Field(None, alias="SUPPORT_CONTACT_VALUE")


class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    origins: str | None = Field(None, alias="BACKEND_CORS_ORIGINS")
    origin_regex: str | None = Field(None, alias="BACKEND_CORS_ORIGIN_REGEX")


class CacheSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    enabled: bool = Field(True, alias="CACHE_ENABLED")
    memcache_url: str = Field("memcached:11211", alias="MEMCACHE_URL")
    ttl_seconds: int = Field(300, alias="CACHE_TTL_SECONDS")


class ObjectStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    enabled: bool = Field(False, alias="S3_ENABLED")
    endpoint_url: str | None = Field(None, alias="AWS_S3_ENDPOINT_URL")
    bucket: str = Field("ecg-images", alias="AWS_S3_BUCKET")
    region: str = Field("us-east-1", alias="AWS_DEFAULT_REGION")
    access_key_id: str | None = Field(None, alias="AWS_ACCESS_KEY_ID")
    secret_access_key: str | None = Field(None, alias="AWS_SECRET_ACCESS_KEY")


class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    level: str = Field("INFO", alias="LOG_LEVEL")
    uvicorn_access_level: str = Field("INFO", alias="UVICORN_ACCESS_LOG_LEVEL")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    support: SupportSettings = Field(default_factory=SupportSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    object_storage: ObjectStorageSettings = Field(default_factory=ObjectStorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    config_dir: str = "app/config"


def get_settings() -> Settings:
    return Settings()
