#!/usr/bin/env bash
# Pourquoi : les volumes Docker nommés des trois environnements (pgdata TimescaleDB, Garage,
# Airflow, Prometheus, Grafana) vivent en clair sous /var/lib/docker/volumes ; Garage n'a pas de
# chiffrement côté serveur et PostgreSQL communautaire n'a pas de TDE (issue #42, ADR 0020).
# coffre-luks.sh pose un coffre LUKS2 dans un fichier image creux, le monte, puis bind-monte
# /var/lib/docker/volumes depuis ce coffre : les trois projets Compose sont chiffrés au repos
# sans qu'un fichier Compose change. La clé vit sur le même disque que l'image : le coffre
# protège une copie isolée de l'image ou du disque (snapshot, sauvegarde, décommissionnement),
# pas le vol du disque entier ni un root sur l'hôte allumé, qui lit le montage en clair.
# Piège : le drop-in RequiresMountsFor sur docker.service est la seule barrière qui empêche
# Docker de recréer des volumes en clair si le coffre manque au démarrage ; retirer la ligne
# fstab du bind la désactive sans message. `nofail` partout, sinon un coffre absent envoie la
# machine en mode urgence et coupe SSH. Bind et drop-in ne sont posés qu'avec la migration :
# posés avant, un redémarrage masquerait les volumes en clair sous un coffre vide. Rejouable.

set -euo pipefail

COFFRE_IMAGE="${COFFRE_IMAGE:-/srv/enervision/coffre.img}"
COFFRE_CLE="${COFFRE_CLE:-/root/enervision-coffre.key}"
COFFRE_MONTAGE="${COFFRE_MONTAGE:-/srv/enervision/coffre}"
COFFRE_TAILLE="${COFFRE_TAILLE:-30G}"
COFFRE_MIGRER="${COFFRE_MIGRER:-0}"
MAPPER="enervision-coffre"
PERIPHERIQUE="/dev/mapper/$MAPPER"
VOLUMES="/var/lib/docker/volumes"
SOURCE_BIND="$COFFRE_MONTAGE/docker-volumes"
DROPIN="/etc/systemd/system/docker.service.d/enervision-coffre.conf"
APT_A_JOUR=0

erreur() { echo "erreur : $*" >&2; exit 1; }

if [[ $# -gt 0 ]]; then
    echo "Usage : [COFFRE_TAILLE=30G] [COFFRE_MIGRER=1] [COFFRE_IMAGE=...] [COFFRE_CLE=...] [COFFRE_MONTAGE=...] $0" >&2
    exit 2
fi

installer() {
    local paquet="$1"
    dpkg -s "$paquet" >/dev/null 2>&1 && return 0
    if [[ $APT_A_JOUR -eq 0 ]]; then
        apt-get update -qq
        APT_A_JOUR=1
    fi
    apt-cache show "$paquet" >/dev/null 2>&1 || return 1
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "$paquet" >/dev/null
    echo "$paquet installé"
}

verifier_prerequis() {
    [[ "$(id -u)" -eq 0 ]] || erreur "à lancer en root"
    [[ "$COFFRE_IMAGE" != /var/lib/docker/* ]] \
        || erreur "l'image $COFFRE_IMAGE ne doit pas vivre sous /var/lib/docker, que le coffre recouvre"
    installer cryptsetup || erreur "cryptsetup introuvable dans apt"
    # Debian 13 sépare le générateur crypttab dans systemd-cryptsetup ; sans lui, crypttab est ignoré.
    installer systemd-cryptsetup || echo "systemd-cryptsetup absent d'apt : le générateur crypttab est dans systemd"
    installer rsync || erreur "rsync introuvable dans apt"
    for outil in truncate blkid findmnt lsblk mkfs.ext4 systemctl; do
        command -v "$outil" >/dev/null || erreur "$outil absent"
    done
}

deja_sur_le_coffre() {
    [[ "$(findmnt -n -o SOURCE "$VOLUMES" 2>/dev/null || true)" == *"$MAPPER"* ]]
}

poser_cle() {
    if [[ ! -f "$COFFRE_CLE" ]]; then
        (umask 077 && head -c 64 /dev/urandom > "$COFFRE_CLE")
        echo "clé générée : $COFFRE_CLE"
    fi
    chmod 400 "$COFFRE_CLE"
}

poser_image() {
    if [[ ! -f "$COFFRE_IMAGE" ]]; then
        mkdir -p "$(dirname "$COFFRE_IMAGE")"
        (umask 077 && truncate -s "$COFFRE_TAILLE" "$COFFRE_IMAGE")
        echo "image creuse créée : $COFFRE_IMAGE ($COFFRE_TAILLE)"
    fi
    if ! cryptsetup isLuks "$COFFRE_IMAGE"; then
        [[ -z "$(blkid -p -o value -s TYPE "$COFFRE_IMAGE" 2>/dev/null || true)" ]] \
            || erreur "$COFFRE_IMAGE porte déjà des données hors LUKS, refus de le formater"
        cryptsetup luksFormat --type luks2 --batch-mode --key-file "$COFFRE_CLE" "$COFFRE_IMAGE"
        echo "image formatée en LUKS2"
    fi
    if [[ ! -e "$PERIPHERIQUE" ]]; then
        cryptsetup open --key-file "$COFFRE_CLE" "$COFFRE_IMAGE" "$MAPPER"
    fi
    if [[ -z "$(blkid -p -o value -s TYPE "$PERIPHERIQUE" 2>/dev/null || true)" ]]; then
        mkfs.ext4 -q -L "$MAPPER" "$PERIPHERIQUE"
        echo "système de fichiers ext4 créé dans le coffre"
    fi
    mkdir -p "$COFFRE_MONTAGE"
    if ! findmnt -n -M "$COFFRE_MONTAGE" >/dev/null; then
        mount "$PERIPHERIQUE" "$COFFRE_MONTAGE"
    fi
    mkdir -p "$SOURCE_BIND"
}

fstab_contient() {
    local cible="$1"
    awk -v cible="$cible" '$1 !~ /^#/ && $2 == cible { trouve = 1 } END { exit !trouve }' /etc/fstab
}

poser_persistance() {
    touch /etc/crypttab
    if ! awk -v nom="$MAPPER" '$1 == nom { trouve = 1 } END { exit !trouve }' /etc/crypttab; then
        echo "$MAPPER $COFFRE_IMAGE $COFFRE_CLE luks,nofail" >> /etc/crypttab
        echo "crypttab : $MAPPER ajouté"
    fi
    if ! fstab_contient "$COFFRE_MONTAGE"; then
        echo "$PERIPHERIQUE $COFFRE_MONTAGE ext4 defaults,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
        echo "fstab : $COFFRE_MONTAGE ajouté"
    fi
    systemctl daemon-reload
}

poser_bind() {
    if ! fstab_contient "$VOLUMES"; then
        echo "$SOURCE_BIND $VOLUMES none bind,nofail 0 0" >> /etc/fstab
        echo "fstab : bind de $VOLUMES ajouté"
    fi
    if [[ ! -f "$DROPIN" ]]; then
        mkdir -p "$(dirname "$DROPIN")"
        cat > "$DROPIN" <<CONF
# Écrit par scripts/coffre-luks.sh (ADR 0020) : coffre absent au démarrage, Docker ne démarre
# pas, plutôt que de recréer des volumes en clair sous $VOLUMES.
[Unit]
RequiresMountsFor=$VOLUMES
CONF
        echo "drop-in : $DROPIN écrit"
    fi
    systemctl daemon-reload
}

empreinte() {
    local dossier="$1"
    find "$dossier" -type f -printf '%s\n' | awk '{ n++; s += $1 } END { printf "%d fichiers, %d octets", n, s }'
}
libre() {
    local dossier="$1"
    df -B1 --output=avail "$dossier" | tail -1 | tr -d ' '
}

expliquer_migration() {
    cat <<FIN

Le coffre est prêt, mais $VOLUMES n'y est pas encore : rien n'a changé pour Docker, un redémarrage
est sans risque. La migration arrête Docker, donc les trois environnements, le temps de copier les
volumes (une à trois minutes), puis le redémarre.
  Volumes à copier : $(du -sh "$VOLUMES" | cut -f1), libre sur le coffre : $(df -h --output=avail "$COFFRE_MONTAGE" | tail -1 | tr -d ' ')
  Libre sur le disque qui porte l'image, la copie occupant deux fois la place jusqu'à la
  suppression de $VOLUMES.avant-coffre : $(df -h --output=avail "$(dirname "$COFFRE_IMAGE")" | tail -1 | tr -d ' ')
Pour la jouer : COFFRE_MIGRER=1 bash $0
FIN
    exit 1
}

migrer() {
    local origine copie
    mkdir -p "$VOLUMES"
    if [[ -z "$(ls -A "$VOLUMES")" ]]; then
        systemctl stop docker.socket docker.service
        poser_bind
        mount "$VOLUMES"
        systemctl start docker.socket docker.service
        echo "aucun volume à migrer : bind monté, Docker redémarré"
        return 0
    fi
    [[ "$COFFRE_MIGRER" == 1 ]] || expliquer_migration
    if docker info 2>/dev/null | grep -q "Live Restore Enabled: true"; then
        erreur "live-restore actif : les conteneurs survivraient à l'arrêt du démon, volumes en clair ouverts. Le désactiver dans /etc/docker/daemon.json avant de migrer"
    fi
    [[ "$(du -sb "$VOLUMES" | cut -f1)" -lt "$(libre "$COFFRE_MONTAGE")" ]] \
        || erreur "le coffre est trop petit pour $VOLUMES ($(du -sh "$VOLUMES" | cut -f1)) : relancer avec une image plus grande"

    echo "arrêt de Docker : les trois environnements sont coupés le temps de la copie"
    systemctl stop docker.socket docker.service
    poser_bind
    rsync -aHAX --numeric-ids "$VOLUMES/" "$SOURCE_BIND/"
    origine="$(empreinte "$VOLUMES")"
    copie="$(empreinte "$SOURCE_BIND")"
    [[ "$origine" == "$copie" ]] \
        || erreur "copie incomplète : $origine dans $VOLUMES, $copie dans $SOURCE_BIND. Docker est arrêté, rien n'a été déplacé"
    echo "copie vérifiée : $copie"
    mv "$VOLUMES" "$VOLUMES.avant-coffre"
    mkdir "$VOLUMES"
    if ! mount "$VOLUMES" || ! deja_sur_le_coffre; then
        umount "$VOLUMES" 2>/dev/null || true
        rmdir "$VOLUMES"
        mv "$VOLUMES.avant-coffre" "$VOLUMES"
        erreur "bind impossible à monter depuis le coffre : $VOLUMES remis en place, Docker reste arrêté"
    fi
    systemctl start docker.socket docker.service
    docker volume ls
}

afficher_etat() {
    echo
    losetup -j "$COFFRE_IMAGE" 2>/dev/null || true
    lsblk "$PERIPHERIQUE" 2>/dev/null || true
    findmnt "$VOLUMES" || echo "$VOLUMES n'est pas un point de montage"
    cat <<FIN

À faire par l'opérateur :
  1. Sauvegarder la clé hors de la VM, sans elle le coffre est perdu :
       scp root@$(hostname -I | awk '{print $1}'):$COFFRE_CLE <emplacement sûr, hors de la machine>
  2. Redémarrer la machine pour valider l'ordonnancement crypttab, fstab, docker, puis vérifier :
       findmnt $VOLUMES && docker ps
FIN
    if [[ -d "$VOLUMES.avant-coffre" ]]; then
        cat <<FIN
  3. Seulement après ce redémarrage validé, supprimer la copie en clair (non effaçable physiquement) :
       rm -rf $VOLUMES.avant-coffre
FIN
    fi
}

verifier_prerequis
if deja_sur_le_coffre; then
    echo "$VOLUMES est déjà servi par le coffre $MAPPER, rien à faire"
    afficher_etat
    exit 0
fi
poser_cle
poser_image
poser_persistance
migrer
afficher_etat
