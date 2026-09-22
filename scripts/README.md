# Scripts

Outillage local du monorepo. Les taches courantes passent par le `Makefile` racine.

## dast-token.sh

Prépare le scan DAST (`.github/workflows/dast.yml`) : sur une API déjà démarrée, crée un compte
`lecteur` jetable, lui fait passer le changement de mot de passe obligatoire et écrit son jeton
d'accès sur la sortie standard. À lancer depuis `apps/backend`, contre une base **jetable** (il y
crée deux comptes) : `BASE_URL=http://localhost:8000 ../../scripts/dast-token.sh`. Nécessite `curl`,
`jq` et `openssl`.
