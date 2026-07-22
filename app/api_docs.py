from fastapi import FastAPI

from app.schemas import ErrorResponse


OPENAPI_TAGS = [
    {
        "name": "Sistema",
        "description": "Disponibilidade da API e de suas dependencias operacionais.",
    },
    {
        "name": "Autenticacao",
        "description": "Identidade do usuario autenticado pelo Amazon Cognito.",
    },
    {
        "name": "Validacao",
        "description": "Contexto diario, fila e decisoes do ciclo de validacao.",
    },
    {
        "name": "Suporte",
        "description": "Informacoes de contato para suporte da plataforma.",
    },
    {
        "name": "Exames",
        "description": "Consulta, rascunhos, status e conclusao dos exames de ECG.",
    },
    {
        "name": "Diagnosticos",
        "description": "Diagnosticos, decisoes medicas e regioes marcadas no ECG.",
    },
    {
        "name": "Dashboard",
        "description": "Indicadores consolidados da fila e das validacoes.",
    },
]

AUTH_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Token ausente, invalido ou expirado."},
    403: {"model": ErrorResponse, "description": "Usuario sem permissao para o recurso."},
}

AUTH_BAD_REQUEST_RESPONSES = {
    **AUTH_RESPONSES,
    400: {"model": ErrorResponse, "description": "Parametros ou dados invalidos."},
}

AUTH_NOT_FOUND_RESPONSES = {
    **AUTH_RESPONSES,
    404: {"model": ErrorResponse, "description": "Recurso nao encontrado."},
}

AUTH_MUTATION_RESPONSES = {
    **AUTH_NOT_FOUND_RESPONSES,
    400: {"model": ErrorResponse, "description": "Dados ou transicao invalidos."},
}


def configure_openapi(app: FastAPI) -> None:
    generated_openapi = app.openapi

    def custom_openapi() -> dict:
        schema = generated_openapi()
        security_schemes = schema.setdefault("components", {}).setdefault(
            "securitySchemes",
            {},
        )
        if "OAuth2PasswordBearer" in security_schemes:
            security_schemes["OAuth2PasswordBearer"] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Cole o access token JWT obtido no Amazon Cognito. "
                    "O Swagger enviara Authorization: Bearer <token>."
                ),
            }
        return schema

    app.openapi = custom_openapi
