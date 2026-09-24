# 0020 - Chiffrement au repos : coffre LUKS des volumes Docker et SSE-C des archives

- Statut : accepté
- Date : 2026-09-24

## Contexte

L'issue #42 demande que les données de la plateforme soient chiffrées au repos. Tout ce que la
plateforme persiste vit dans les volumes Docker nommés des trois projets Compose de la VM ENI
([ADR 0009](0009-deux-environnements-compose-sur-la-vm-eni.md),
[ADR 0017](0017-environnement-dev-a-la-demande.md)), sous `/var/lib/docker/volumes` : la base
TimescaleDB (`pgdata`, relevés, comptes, audit), les métadonnées et les objets de Garage
(`garage_meta`, `garage_data`, les archives des chunks de `reading` exportées par le DAG
`retention`, [ADR 0019](0019-stockage-objet-garage-et-cycle-de-vie-des-mesures.md)), les journaux et l'état ML d'Airflow, les séries de Prometheus et la base
de Grafana.

Aucun des deux dépôts de données ne chiffre lui-même : Garage n'a pas de chiffrement côté serveur
et sa documentation renvoie à un volume LUKS sous ses données ; PostgreSQL communautaire n'a pas de
chiffrement transparent des données (TDE), et l'image `timescaledb-ha` n'en ajoute pas. La VM est
unique, sur un seul disque virtuel, sans partition libre, sans TPM, et personne n'est devant sa
console au démarrage : tout redémarrage doit aboutir sans saisie.

## Décision

**Un coffre LUKS2 sous tous les volumes Docker, posé par `scripts/coffre-luks.sh`.**

- Le coffre est un **fichier image creux** (`/srv/enervision/coffre.img`, 30 Go par défaut)
  formaté en **LUKS2**, ouvert par une **clé de 64 octets tirée de `/dev/urandom`**, lisible par
  root seulement (`/root/enervision-coffre.key`, `0400`). Un fichier plutôt qu'une partition : la
  VM n'en a pas de libre, et l'image se déplace ou se sauvegarde comme un fichier.
- Le mapper `enervision-coffre` porte un ext4 monté sur `/srv/enervision/coffre`, et
  `/var/lib/docker/volumes` est **bind-monté** depuis `/srv/enervision/coffre/docker-volumes`.
  Docker ne voit qu'un dossier ordinaire : ni `data-root`, ni les fichiers Compose, ni les noms
  de volumes ne changent, et les trois environnements sont couverts d'un coup.
- L'ouverture et les montages sont déclarés dans **`/etc/crypttab` et `/etc/fstab`, avec
  `nofail`** sur les trois lignes : un coffre absent ne doit jamais envoyer la machine en mode
  urgence, où SSH ne répond plus. Sur Debian 13 le générateur crypttab est dans le paquet
  `systemd-cryptsetup`, installé par le script s'il existe dans apt.
- Un **drop-in `RequiresMountsFor=/var/lib/docker/volumes`** sur `docker.service` fait la
  barrière : sans le bind, Docker ne démarre pas, plutôt que de recréer des volumes vides en
  clair et de laisser trois stacks se lever sur des bases neuves.
- Le script est **rejouable** : clé, image, formatage, système de fichiers, crypttab, fstab et
  drop-in ne sont posés que s'ils manquent, et il sort sans rien toucher si
  `/var/lib/docker/volumes` est déjà servi par le coffre. La **migration à froid** des volumes
  existants n'a lieu qu'avec `COFFRE_MIGRER=1` : refus si `live-restore` est actif, arrêt de
  `docker.socket` et `docker.service`, `rsync -aHAX --numeric-ids`, comparaison du nombre et de la
  taille des fichiers, puis bascule du dossier et redémarrage de Docker. L'ancien dossier reste en
  `/var/lib/docker/volumes.avant-coffre` jusqu'à validation par un redémarrage.
- Terraform peut le jouer : `null_resource.coffre`, activé par `coffre_taille` non vide,
  s'exécute après Docker et avant `provision-host.sh`. La ressource est optionnelle et absente du
  plan tant que la variable est vide.

**SSE-C sur les archives exportées vers Garage.** Le module d'export du DAG `retention` envoie
chaque archive avec une clé client (`GARAGE_SSE_KEY`, générée dans le `.env` par
`provision-host.sh`) ; Garage la chiffre en AES-256-GCM et n'en garde que l'empreinte. Les objets
sont donc chiffrés une seconde fois, avec une clé distincte de celle du coffre, dans le seul
dépôt que l'on pourrait un jour sortir de la VM.

## Alternatives écartées

| Écartée | Raison |
|---|---|
| `pgcrypto`, chiffrement par colonne | Ne couvre ni les index, ni les journaux WAL, ni Garage, ni Airflow ; la clé serait dans l'application, à côté des données, pour un coût de développement et de requête sur chaque lecture d'hypertable. |
| Déplacer le `data-root` de Docker dans le coffre | Chiffre aussi les images et les couches, sans valeur, et impose de recopier tout `/var/lib/docker` : plus long, plus de place, et le démon doit être reconfiguré. Seuls les volumes portent des données. |
| Chiffrer côté client dans le module d'export | Couvre les archives et rien d'autre, avec une bibliothèque cryptographique à porter dans le code métier alors que Garage offre SSE-C. Retenu seulement sous cette forme, en complément du coffre. |
| Volume Docker chiffré par un plugin | Un plugin tiers par volume nommé, à installer et suivre sur la machine, pour huit volumes par environnement ; le coffre les couvre tous d'un bind. |
| Disque ou partition dédiée | La VM n'a qu'un disque virtuel, sans partition libre, et son redimensionnement n'est pas dans les mains de l'équipe. |
| Clé saisie au démarrage | Personne devant la console ; un redémarrage de la VM par l'école laisserait la plateforme arrêtée jusqu'à intervention. |
| Clé scellée dans un TPM | La VM n'en expose pas. |

## Conséquences

- **Ce que le coffre protège, et ce qu'il ne protège pas.** La clé et l'image vivent sur le même
  disque. Le coffre protège une copie isolée de l'image ou du disque : snapshot, sauvegarde,
  décommissionnement du disque virtuel. Il ne protège ni du vol du disque entier, où la clé se
  trouve aussi, ni d'un root sur l'hôte allumé, qui lit le montage en clair. La copie
  `.avant-coffre`, supprimée après validation, n'est pas effaçable physiquement sur un disque
  virtuel. La clé SSE-C transite en clair sur le réseau Compose interne, entre `airflow-scheduler`
  et Garage, à chaque objet envoyé.
- **Perte de la clé, perte de tout.** Sans `/root/enervision-coffre.key`, l'image est illisible
  et les trois bases avec elle. La clé est à sauvegarder hors de la VM tout de suite après la
  pose, dans un emplacement que seuls les administrateurs lisent.
- **Coupure lors de la migration.** La copie des volumes se fait Docker arrêté : les trois
  environnements sont indisponibles une à trois minutes, et le disque doit porter deux fois la
  taille des volumes jusqu'à la suppression de `.avant-coffre`.
- **Redémarrage de test obligatoire.** L'ordonnancement crypttab, fstab, drop-in ne se vérifie
  qu'en redémarrant : `findmnt /var/lib/docker/volumes` et `docker ps` après le reboot, avant de
  supprimer la copie en clair.
- **Docker dépend du coffre.** Si l'image ou la clé disparaît, Docker refuse de démarrer
  (`dependency failed`) et la machine reste joignable par SSH ; c'est voulu. Retirer la ligne
  fstab du bind retire cette protection sans message.
- **Rotation.** La clé LUKS se change par `cryptsetup luksChangeKey` sans réécrire les données.
  `GARAGE_SSE_KEY` ne se change pas sans réécrire chaque objet : Garage n'a pas de re-chiffrement
  côté serveur, et un objet écrit avec l'ancienne clé ne se lit qu'avec elle.
- **Terraform interrompt la stack, une fois.** La première pose avec `coffre_taille` est la seule
  ressource de `vm-eni` qui arrête Docker, en contradiction assumée avec
  l'[ADR 0010](0010-terraform-provisionne-github-actions-deploie.md) pour cette seule occasion ;
  les `apply` suivants trouvent le coffre en place et n'y touchent pas.
