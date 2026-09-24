# Scripts

Outillage local du monorepo. Les taches courantes passent par le `Makefile` racine.

## dast-token.sh

Prépare le scan DAST (`.github/workflows/dast.yml`) : sur une API déjà démarrée, crée un compte
`lecteur` jetable, lui fait passer le changement de mot de passe obligatoire et écrit son jeton
d'accès sur la sortie standard. À lancer depuis `apps/backend`, contre une base **jetable** (il y
crée deux comptes) : `BASE_URL=http://localhost:8000 ../../scripts/dast-token.sh`. Nécessite `curl`,
`jq` et `openssl`.

## coffre-luks.sh

Pose un coffre LUKS2 dans un fichier image creux et bind-monte `/var/lib/docker/volumes` depuis ce
coffre : les volumes des trois environnements de la VM sont chiffrés au repos sans toucher aux
fichiers Compose (issue #42, [ADR 0020](../docs/adr/0020-chiffrement-au-repos-coffre-luks-et-sse-c.md)).
Rejouable, en root sur la VM : `COFFRE_TAILLE=30G COFFRE_MIGRER=1 bash scripts/coffre-luks.sh`. Sans
`COFFRE_MIGRER=1`, le coffre est préparé mais les volumes existants ne sont pas déplacés : la
migration arrête Docker le temps de la copie. Variables : `COFFRE_IMAGE`, `COFFRE_CLE`,
`COFFRE_MONTAGE`, `COFFRE_TAILLE`. La clé est à sauvegarder hors de la VM : perdue, tout est perdu.
