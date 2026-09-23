#!/usr/bin/env bash
# Contrainte : réservé à une base JETABLE (CI, e2e, charge sur le poste) - comptes-test.sh. Crée
# un administrateur par la CLI, puis un lecteur et un opérateur, et écrit leurs identifiants en
# JSON dans $COMPTES_FICHIER.
# Piège : un compte neuf est en `must_change_password`, que toute route gardée refuse. Chaque
# compte passe donc le changement de mot de passe avant d'être écrit dans le fichier.
# Piège : `create-admin` refuse un second administrateur actif. ADMIN_SUPPLEMENTAIRE=1 passe
# `--force`, pour la base du poste ; jamais en recette, où les comptes se créent par l'interface.
#
# BASE_URL vise l'API (http://localhost:8000 par défaut, ou le proxy en https). APP_CLI lance la
# CLI du backend : depuis apps/backend par défaut, ou `docker compose ... exec -T backend python
# -m app.cli` contre la stack conteneurisée.

set -euo pipefail
# Sans lui, une erreur dans `$(...)` ne s'arrête pas : la substitution rendrait un mot de passe vide.
shopt -s inherit_errexit

BASE_URL="${BASE_URL:-http://localhost:8000}"
API="$BASE_URL/api/v1"
COMPTES_FICHIER="${COMPTES_FICHIER:?COMPTES_FICHIER=chemin du fichier JSON requis}"
read -ra CLI <<<"${APP_CLI:-uv run --frozen --no-sync --no-build python -m app.cli}"
SUFFIXE="$(openssl rand -hex 4)"

CURL=(curl -fsS)
[[ "$BASE_URL" == https://* ]] && CURL+=(--insecure)

# Classes exigées par le validateur : majuscule, minuscule, chiffre, caractère spécial.
nouveau_mot_de_passe() { echo "Test-$(openssl rand -hex 12)-Aa1!"; }

journal() { echo "comptes-test: $*" >&2; }

connexion() {
    local email="$1" mot_de_passe="$2"
    "${CURL[@]}" -X POST "$API/auth/login" -H 'Content-Type: application/json' \
        -d "$(jq -n --arg e "$email" --arg p "$mot_de_passe" '{email:$e, password:$p}')" \
        | jq -r '.access_token'
}

# `/auth/password` rend un nouveau jeton d'accès : pas de reconnexion, donc pas de second hachage
# Argon2id ni de requête de plus dans la zone `auth` de nginx (30 par minute).
changer_mot_de_passe() {
    local jeton="$1" ancien="$2" nouveau="$3"
    "${CURL[@]}" -X POST "$API/auth/password" \
        -H "Authorization: Bearer $jeton" -H 'Content-Type: application/json' \
        -d "$(jq -n --arg a "$ancien" --arg n "$nouveau" '{current_password:$a, new_password:$n}')" \
        | jq -r '.access_token'
}

creer_compte() {
    local jeton_admin="$1" email="$2" role="$3" reponse temporaire
    reponse="$("${CURL[@]}" -X POST "$API/users" -H "Authorization: Bearer $jeton_admin" \
        -H 'Content-Type: application/json' \
        -d "$(jq -n --arg e "$email" --arg r "$role" '{email:$e, role:$r}')")"
    temporaire="$(jq -r '.temporary_password // empty' <<<"$reponse")"
    [[ -n "$temporaire" ]] || { journal "mot de passe temporaire absent de la réponse : $reponse"; exit 1; }
    echo "$temporaire"
}

# Rend le mot de passe définitif d'un compte créé par `creer_compte`.
activer_compte() {
    local email="$1" temporaire="$2" definitif jeton
    definitif="$(nouveau_mot_de_passe)"
    jeton="$(connexion "$email" "$temporaire")"
    changer_mot_de_passe "$jeton" "$temporaire" "$definitif" >/dev/null
    echo "$definitif"
}

EMAIL_ADMIN="test-admin-$SUFFIXE@enervision.fr"
journal "création de l'administrateur $EMAIL_ADMIN"
OPTIONS_ADMIN=(--email "$EMAIL_ADMIN" --generate)
[[ "${ADMIN_SUPPLEMENTAIRE:-0}" == "1" ]] && OPTIONS_ADMIN+=(--force)
if ! SORTIE="$("${CLI[@]}" create-admin "${OPTIONS_ADMIN[@]}")"; then
    journal "la création de l'administrateur a échoué : $SORTIE"
    exit 1
fi
MDP_TEMPORAIRE_ADMIN="$(sed -n 's/^Mot de passe généré, il ne sera plus affiché : //p' <<<"$SORTIE" | tr -d '\r')"
[[ -n "$MDP_TEMPORAIRE_ADMIN" ]] || { journal "mot de passe introuvable dans la sortie : $SORTIE"; exit 1; }

MDP_ADMIN="$(nouveau_mot_de_passe)"
JETON_ADMIN="$(connexion "$EMAIL_ADMIN" "$MDP_TEMPORAIRE_ADMIN")"
JETON_ADMIN="$(changer_mot_de_passe "$JETON_ADMIN" "$MDP_TEMPORAIRE_ADMIN" "$MDP_ADMIN")"

EMAIL_LECTEUR="test-lecteur-$SUFFIXE@enervision.fr"
EMAIL_OPERATEUR="test-operateur-$SUFFIXE@enervision.fr"
journal "création du lecteur et de l'opérateur"
TEMPORAIRE_LECTEUR="$(creer_compte "$JETON_ADMIN" "$EMAIL_LECTEUR" lecteur)"
MDP_LECTEUR="$(activer_compte "$EMAIL_LECTEUR" "$TEMPORAIRE_LECTEUR")"
TEMPORAIRE_OPERATEUR="$(creer_compte "$JETON_ADMIN" "$EMAIL_OPERATEUR" operateur)"
MDP_OPERATEUR="$(activer_compte "$EMAIL_OPERATEUR" "$TEMPORAIRE_OPERATEUR")"

umask 077
jq -n \
    --arg ae "$EMAIL_ADMIN" --arg ap "$MDP_ADMIN" \
    --arg le "$EMAIL_LECTEUR" --arg lp "$MDP_LECTEUR" \
    --arg oe "$EMAIL_OPERATEUR" --arg op "$MDP_OPERATEUR" \
    '{
        admin: {email: $ae, password: $ap},
        lecteur: {email: $le, password: $lp},
        operateur: {email: $oe, password: $op}
    }' >"$COMPTES_FICHIER"
journal "identifiants écrits dans $COMPTES_FICHIER"
