#!/bin/sh
# Contrainte : certbot écrit dans /etc/letsencrypt/live/<domaine>/, nginx lit /etc/nginx/tls/.
# Ce hook recopie le résultat à l'emplacement unique que la configuration nginx connaît, ce
# qui rend le mode auto-signé et le mode ACME interchangeables sans toucher à un vhost.

set -eu

cp -L "$RENEWED_LINEAGE/fullchain.pem" /tls/fullchain.pem
cp -L "$RENEWED_LINEAGE/privkey.pem" /tls/privkey.pem
chmod 644 /tls/fullchain.pem
chmod 600 /tls/privkey.pem
