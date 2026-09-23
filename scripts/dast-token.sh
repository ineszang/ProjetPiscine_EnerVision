#!/usr/bin/env bash
# Prépare le scan DAST : crée un compte `lecteur` sur une API déjà démarrée, lui fait passer le
# changement de mot de passe obligatoire, et écrit son jeton d'accès sur la sortie standard.
#
# Piège : un compte neuf est en `must_change_password`, et toute route gardée le refuse tant que
# le mot de passe n'a pas été changé. Sans cette étape, ZAP ne verrait que 403 sur les routes
# gardées et le scan ne testerait rien de l'API authentifiée.
#
# Contrainte : le compte du scan est `lecteur`, jamais `admin`. Un scan actif avec un jeton admin
# frapperait POST /users ou la réinitialisation de mots de passe pour de bon.
#
# L'administrateur n'existe que pour créer ce compte (l'API n'a pas d'inscription publique).
# À lancer depuis apps/backend, dans un environnement où DATABASE_URL et APP_SECRET_KEY visent
# une base JETABLE : le script y crée deux comptes.

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API="$BASE_URL/api/v1"
SUFFIXE="$(openssl rand -hex 4)"
EMAIL_ADMIN="dast-admin-$SUFFIXE@enervision.fr"
EMAIL_LECTEUR="dast-lecteur-$SUFFIXE@enervision.fr"

# Classes exigées par le validateur : majuscule, minuscule, chiffre, caractère spécial.
nouveau_mot_de_passe() { echo "Dast-$(openssl rand -hex 12)-Aa1!"; }

# Tout ce qui n'est pas la sortie finale part sur stderr : la sortie standard ne porte que le jeton.
journal() { echo "dast-token: $*" >&2; }

connexion() {
    local email="$1" mot_de_passe="$2"
    curl -fsS -X POST "$API/auth/login" -H 'Content-Type: application/json' \
        -d "$(jq -n --arg e "$email" --arg p "$mot_de_passe" '{email:$e, password:$p}')" \
        | jq -r '.access_token'
}

# Rend le nouveau jeton d'accès : `/auth/password` en émet un (avec l'`iat` de la session en
# cours, cf. le piège documenté dans `app/api/deps.py`), pas seulement une confirmation. S'y fier
# évite une reconnexion, donc un second hachage Argon2id (19456 Kio) et un aller-retour de
# refresh-token superflus sur le chemin critique de la CI.
changer_mot_de_passe() {
    local jeton="$1" ancien="$2" nouveau="$3"
    curl -fsS -X POST "$API/auth/password" \
        -H "Authorization: Bearer $jeton" -H 'Content-Type: application/json' \
        -d "$(jq -n --arg a "$ancien" --arg n "$nouveau" '{current_password:$a, new_password:$n}')" \
        | jq -r '.access_token'
}

journal "création de l'administrateur $EMAIL_ADMIN"
if ! SORTIE="$(uv run --frozen --no-sync --no-build python -m app.cli create-admin --email "$EMAIL_ADMIN" --generate)"; then
    journal "la création de l'administrateur a échoué :"
    journal "$SORTIE"
    exit 1
fi
MDP_ADMIN="$(sed -n 's/^Mot de passe généré, il ne sera plus affiché : //p' <<<"$SORTIE")"
[[ -n "$MDP_ADMIN" ]] || { journal "mot de passe administrateur introuvable dans la sortie :"; journal "$SORTIE"; exit 1; }

JETON="$(connexion "$EMAIL_ADMIN" "$MDP_ADMIN")"
NOUVEAU_ADMIN="$(nouveau_mot_de_passe)"
JETON="$(changer_mot_de_passe "$JETON" "$MDP_ADMIN" "$NOUVEAU_ADMIN")"

journal "création du lecteur $EMAIL_LECTEUR"
REPONSE="$(curl -fsS -X POST "$API/users" -H "Authorization: Bearer $JETON" \
    -H 'Content-Type: application/json' \
    -d "$(jq -n --arg e "$EMAIL_LECTEUR" '{email:$e, role:"lecteur"}')")"
MDP_TEMPORAIRE="$(jq -r '.temporary_password // empty' <<<"$REPONSE")"
[[ -n "$MDP_TEMPORAIRE" ]] || { journal "mot de passe temporaire introuvable dans la réponse de POST /users :"; journal "$REPONSE"; exit 1; }

JETON="$(connexion "$EMAIL_LECTEUR" "$MDP_TEMPORAIRE")"
NOUVEAU_LECTEUR="$(nouveau_mot_de_passe)"
JETON="$(changer_mot_de_passe "$JETON" "$MDP_TEMPORAIRE" "$NOUVEAU_LECTEUR")"

# Vérifie que le jeton ouvre bien une route gardée avant de le rendre.
CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$API/sites" -H "Authorization: Bearer $JETON")"
[[ "$CODE" == "200" ]] || { journal "GET /sites répond $CODE avec le jeton du lecteur, attendu 200"; exit 1; }

journal "jeton du lecteur prêt"
echo "$JETON"
