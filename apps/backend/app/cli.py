# Pourquoi : `create_admin()` est une commande et non une révision Alembic. Une révision qui
# insérerait un compte graverait son empreinte dans Git pour toujours, et son mot de passe
# serait connu de quiconque lit le dépôt. L'ADR 0001 pose par ailleurs qu'Alembic porte le
# schéma, pas les données.
# Piège : le mot de passe ne transite jamais par `argv`, visible de tout `ps`, ni par
# l'historique du shell. Il est saisi par `getpass` ou tiré au sort par la commande.

import argparse
import asyncio
import json
import secrets
import string
import sys
from getpass import getpass
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.hashing import build_hasher
from app.core.roles import Role
from app.db.session import get_session_factory
from app.main import create_app
from app.repositories.user import UserRepository
from app.schemas.auth import PASSWORD_MIN_LENGTH, valide_complexite

LONGUEUR_MOT_DE_PASSE_GENERE = 24
CARACTERES_SPECIAUX = "!@#$%^&*()-_=+[]{};:,.?"
CHEMIN_CONTRAT = Path(__file__).resolve().parent.parent / "openapi.json"


async def create_admin(
    settings: Settings, *, email: str, password: str, force: bool
) -> tuple[bool, str]:
    hacheur = build_hasher(
        time_cost=settings.argon2_time_cost,
        memory_cost_kib=settings.argon2_memory_cost_kib,
        parallelism=settings.argon2_parallelism,
        max_concurrency=settings.argon2_max_concurrency,
    )
    empreinte = await hacheur.hash(password)

    async with get_session_factory()() as session:
        depot = UserRepository(session)

        if not force and await depot.count_active_admins() > 0:
            return False, "Un administrateur actif existe déjà, relancer avec --force pour forcer"

        if await depot.get_by_email(email) is not None:
            return False, f"Le compte {email} existe déjà"

        await depot.create(
            email=email,
            password_hash=empreinte,
            role=Role.ADMIN,
            must_change_password=True,
        )
        await session.commit()

    return (
        True,
        f"Administrateur {email.strip().lower()} créé, mot de passe à changer à la connexion",
    )


# Piège : le schéma ne doit dépendre ni du `.env` du poste ni des variables `APP_*`, sinon le
# fichier versionné changerait de machine en machine et le test de dérive deviendrait un oracle
# de configuration locale. Tout ce qui atteint le schéma est donc posé ici, `_env_file` compris.
def settings_du_contrat() -> Settings:
    return Settings(
        _env_file=None,
        name="EnerVision API",
        version="0.1.0",
        env="local",
        api_prefix="/api/v1",
        secret_key=SecretStr("contrat-openapi-sans-effet-sur-le-schema"),
        database_url="postgresql+asyncpg://openapi:contrat@localhost:5432/enervision",
    )


def schema_du_contrat() -> dict[str, Any]:
    schema: dict[str, Any] = create_app(settings_du_contrat()).openapi()
    return schema


def rend_le_contrat() -> str:
    return json.dumps(schema_du_contrat(), indent=2, ensure_ascii=False) + "\n"


def export_openapi(destination: Path) -> str:
    destination.write_text(rend_le_contrat(), encoding="utf-8")
    return f"Contrat OpenAPI écrit dans {destination}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Outils EnerVision")
    sous_commandes = parser.add_subparsers(dest="commande", required=True)

    admin = sous_commandes.add_parser("create-admin", help="Crée le premier administrateur")
    admin.add_argument("--email", required=True)
    admin.add_argument(
        "--generate", action="store_true", help="Tire un mot de passe au sort et l'affiche une fois"
    )
    admin.add_argument(
        "--force", action="store_true", help="Crée le compte même si un administrateur existe"
    )

    contrat = sous_commandes.add_parser(
        "export-openapi", help="Écrit le contrat OpenAPI sur disque"
    )
    contrat.add_argument("--output", default=str(CHEMIN_CONTRAT))
    return parser


def genere_mot_de_passe() -> str:
    tirage = secrets.SystemRandom()
    classes = [
        string.ascii_uppercase,
        string.ascii_lowercase,
        string.digits,
        CARACTERES_SPECIAUX,
    ]
    reste = LONGUEUR_MOT_DE_PASSE_GENERE - len(classes)
    caracteres = [tirage.choice(classe) for classe in classes]
    caracteres += [tirage.choice("".join(classes)) for _ in range(reste)]
    tirage.shuffle(caracteres)
    return "".join(caracteres)


def read_password(*, generate: bool) -> str:
    if generate:
        mot_de_passe = genere_mot_de_passe()
        print(f"Mot de passe généré, il ne sera plus affiché : {mot_de_passe}")
        return mot_de_passe

    mot_de_passe = getpass("Mot de passe : ")
    if len(mot_de_passe) < PASSWORD_MIN_LENGTH:
        raise SystemExit(
            f"Le mot de passe doit faire au moins {PASSWORD_MIN_LENGTH} caractères"
        )
    try:
        valide_complexite(mot_de_passe)
    except ValueError as erreur:
        raise SystemExit(str(erreur)) from erreur
    if mot_de_passe != getpass("Confirmation : "):
        raise SystemExit("Les deux saisies diffèrent")
    return mot_de_passe


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)

    if arguments.commande == "export-openapi":
        print(export_openapi(Path(arguments.output)))
        return 0

    mot_de_passe = read_password(generate=arguments.generate)

    succes, message = asyncio.run(
        create_admin(
            get_settings(),
            email=arguments.email,
            password=mot_de_passe,
            force=arguments.force,
        )
    )
    print(message)
    return 0 if succes else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
