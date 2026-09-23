#!/usr/bin/env bash
# Contrainte : prépare le scan DAST sur une base JETABLE - dast-token.sh. Crée les comptes de
# test (scripts/comptes-test.sh, mêmes variables) et écrit sur la sortie standard le seul jeton
# d'accès du `lecteur`.
# Contrainte : le compte du scan est `lecteur`, jamais `admin`. Un scan actif avec un jeton admin
# frapperait POST /users ou la réinitialisation de mots de passe pour de bon.

set -euo pipefail
shopt -s inherit_errexit

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8000}"
COMPTES="$(mktemp)"
trap 'rm -f "$COMPTES"' EXIT

COMPTES_FICHIER="$COMPTES" BASE_URL="$BASE_URL" "$ICI/comptes-test.sh"

JETON="$(curl -fsS -X POST "$BASE_URL/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "$(jq '.lecteur | {email, password}' "$COMPTES")" | jq -r '.access_token')"

CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/api/v1/sites" -H "Authorization: Bearer $JETON")"
[[ "$CODE" == "200" ]] || { echo "dast-token: GET /sites répond $CODE avec le jeton du lecteur, attendu 200" >&2; exit 1; }

echo "$JETON"
