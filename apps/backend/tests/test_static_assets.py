# Piège : le logo est committé indépendamment à deux endroits (`app/static/`, servi par
# `/docs`/`/redoc`, et `apps/frontend/public/`, servi au front) faute d'étape de build partagée.
# Sans ce test, une mise à jour d'un seul des deux fichiers dérive silencieusement : rien en CI
# ne le détecte.

from pathlib import Path

BACKEND_LOGO = Path(__file__).parent.parent / "app" / "static" / "logo-icon.png"
FRONTEND_LOGO = Path(__file__).parent.parent.parent / "frontend" / "public" / "logo-icon.png"


def test_the_backend_logo_stays_in_sync_with_the_frontend_one() -> None:
    assert BACKEND_LOGO.read_bytes() == FRONTEND_LOGO.read_bytes()
