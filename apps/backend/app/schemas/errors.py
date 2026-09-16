# Piège : ces modèles ne décrivent rien, ils publient. Ce sont eux que Swagger montre, donc ils
# doivent suivre `validation_error_handler()` et `unhandled_error_handler()` d'`app/api/errors.py`
# à la lettre. Un champ renommé là-bas sans l'être ici rend la documentation fausse en silence.

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


class FieldError(BaseModel):
    champ: str
    type: str


class ValidationErrorResponse(BaseModel):
    detail: list[FieldError]


class InternalErrorResponse(BaseModel):
    detail: str
    correlation: str
