#!/usr/bin/env bash
# Contrainte : nginx lit toujours infra/proxy/tls/{fullchain,privkey}.pem, quel que soit le
# mode d'obtention. Ce script remplit ces deux fichiers pour la démonstration, certbot les
# remplit par acme-deploy-hook.sh. La configuration nginx ne connaît pas la différence.

set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESTINATION="$RACINE/infra/proxy/tls"
HOTE="${PUBLIC_HOST:-enervision.local}"
ADRESSE="${PUBLIC_IP:-}"
JOURS="${TLS_DAYS:-365}"
ECRASER=0

for argument in "$@"; do
    case "$argument" in
        --force) ECRASER=1 ;;
        *)
            echo "Usage : PUBLIC_HOST=exemple.local [PUBLIC_IP=10.0.0.10] $0 [--force]" >&2
            exit 2
            ;;
    esac
done

if [[ -f "$DESTINATION/fullchain.pem" && $ECRASER -eq 0 ]]; then
    echo "Un certificat existe déjà dans $DESTINATION." >&2
    echo "Relancer avec --force pour l'écraser." >&2
    exit 1
fi

mkdir -p "$DESTINATION"

NOMS="DNS:$HOTE,DNS:localhost"
if [[ -n "$ADRESSE" ]]; then
    NOMS="$NOMS,IP:$ADRESSE"
fi

openssl req -x509 -nodes -newkey rsa:2048 -sha256 -days "$JOURS" \
    -subj "/CN=$HOTE" \
    -addext "subjectAltName=$NOMS" \
    -keyout "$DESTINATION/privkey.pem" \
    -out "$DESTINATION/fullchain.pem" 2>/dev/null

chmod 600 "$DESTINATION/privkey.pem"
chmod 644 "$DESTINATION/fullchain.pem"

echo "Certificat auto-signé écrit dans $DESTINATION."
echo "  Noms couverts : $NOMS"
echo "  Validité      : $JOURS jours"
echo "Le navigateur avertira d'un émetteur inconnu, c'est attendu hors Let's Encrypt."
