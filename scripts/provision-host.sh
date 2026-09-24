#!/usr/bin/env bash
# Pourquoi : la machine porte trois environnements, chacun un clone du dépôt, un `.env` et un
# projet Compose (ADR 0009, 0017), derrière un frontal SNI sur 443 (ADR 0018). Ce script prépare
# la machine et les trois dossiers sans démarrer aucune stack : c'est le rôle du runner.
# Piège : le script, et non le `.env.example` du clone, fait foi pour les secrets (GENERATEURS)
# et l'adressage (tableau du bas). Un `.env` existant garde ses secrets, reçoit ceux qui lui
# manquent et voit son adressage réaligné : sans ça, un `.env` né avant une clé ne la reçoit
# jamais, et le clone de la prod, en retard sur `main`, ne connaîtrait pas les nouvelles.
# Piège : lancé en root, git refuse un clone déjà chowné au runner (propriété douteuse). D'où
# `safe.directory` passé en ligne de commande, seule portée où git l'accepte - preparer().
# Rejouable : un certificat n'est refait que s'il ne couvre plus l'hôte, et celui de Let's Encrypt
# n'est renouvelé qu'à échéance.

set -euo pipefail

DEPOT="${REPO_URL:-https://github.com/ineszang/ProjetPiscine_EnerVision.git}"
RACINE="${RACINE:-/srv/enervision}"
DOMAINE="${DOMAINE:-enervision-g3.dynv6.net}"
ADRESSE="${PUBLIC_IP:-$(hostname -I | awk '{print $1}')}"
PROPRIETAIRE="${PROPRIETAIRE:-${SUDO_USER:-}}"
JETON_DNS="$RACINE/dns.token"
COMPOSE_MINIMALE="2.24.4"

erreur() { echo "erreur : $*" >&2; exit 1; }
secret() { openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-48; }
court() { secret | cut -c1-20; }
# Clé Fernet : 32 octets en base64 urlsafe, padding compris.
fernet() { openssl rand -base64 32 | tr '+/' '-_'; }
# Garage : rpc_secret et secret de clé S3 en 32 octets hexadécimaux, identifiant de clé en GK + hex,
# clé SSE-C des archives en 32 octets base64 (ADR 0019, 0020).
hex32() { openssl rand -hex 32; }
cle_acces() { echo "GK$(openssl rand -hex 12)"; }
cle_sse() { openssl rand -base64 32; }

declare -A GENERATEURS=(
    [POSTGRES_PASSWORD]=secret [APP_SECRET_KEY]=secret [AIRFLOW_FERNET_KEY]=fernet
    [AIRFLOW_API_SECRET_KEY]=secret [AIRFLOW_JWT_SECRET]=secret [AIRFLOW_ADMIN_PASSWORD]=court
    [AIRFLOW_APP_SECRET_KEY]=secret [APP_METRICS_TOKEN]=secret [GRAFANA_ADMIN_PASSWORD]=court
    [SUPERVISION_DB_PASSWORD]=secret
    [GARAGE_RPC_SECRET]=hex32 [GARAGE_ADMIN_TOKEN]=secret [GARAGE_METRICS_TOKEN]=secret
    [GARAGE_ACCESS_KEY]=cle_acces [GARAGE_SECRET_KEY]=hex32 [GARAGE_SSE_KEY]=cle_sse
)

verifier_outils() {
    for outil in git make openssl curl; do
        command -v "$outil" >/dev/null || erreur "$outil absent (apt-get install $outil)"
    done
    command -v docker >/dev/null || erreur "Docker absent : https://docs.docker.com/engine/install/debian/"
    docker info >/dev/null 2>&1 || erreur "le démon Docker ne répond pas, ou l'utilisateur n'est pas dans le groupe docker"
    local version
    version="$(docker compose version --short 2>/dev/null || true)"
    [[ -n "$version" ]] || erreur "plugin docker compose absent (paquet docker-compose-plugin)"
    [[ "$(printf '%s\n%s\n' "$COMPOSE_MINIMALE" "${version#v}" | sort -V | head -1)" == "$COMPOSE_MINIMALE" ]] \
        || erreur "docker compose $version trop ancien : $COMPOSE_MINIMALE requis pour !override et !reset"
    curl -fsSI --max-time 10 https://github.com >/dev/null || erreur "pas de sortie HTTPS vers github.com"
    echo "docker compose $version, sortie Internet : ok"
}

valeur() { sed -n "s/^$2=//p" "$1" | tail -1; }

poser() {
    local fichier="$1" cle="$2" contenu="$3"
    if grep -q "^$cle=" "$fichier"; then
        CLE="$cle" CONTENU="$contenu" awk -F= '
            $1 == ENVIRON["CLE"] { print ENVIRON["CLE"] "=" ENVIRON["CONTENU"]; next } { print }
        ' "$fichier" > "$fichier.tmp"
        mv "$fichier.tmp" "$fichier"
    else
        printf '%s=%s\n' "$cle" "$contenu" >> "$fichier"
    fi
}

preparer() {
    local env="$1" branche="$2" hote="$3"
    local port_https="$4" port_http="$5" port_front="$6" port_pg="$7" port_mailpit="$8"
    local port_airflow="$9" profils="${10}" port_grafana="${11}" port_prometheus="${12}"
    local port_alertmanager="${13}" port_garage_s3="${14}" port_garage_admin="${15}"
    local dossier="$RACINE/$env"
    local fichier="$dossier/.env" brouillon="$dossier/.env.brouillon" cle oubliees ajoutees=""

    if [[ -d "$dossier/.git" ]]; then
        local git=(git -c "safe.directory=$dossier" -C "$dossier")
        "${git[@]}" fetch --quiet origin "$branche"
        "${git[@]}" checkout --quiet "$branche"
        "${git[@]}" reset --quiet --hard "origin/$branche"
    else
        git clone --quiet --branch "$branche" "$DEPOT" "$dossier"
    fi

    local masque
    masque="$(umask)"
    umask 077
    if [[ -f "$fichier" ]]; then
        cp -p "$fichier" "$brouillon"
        awk -F= 'NR == FNR { connues[$1]; next } /^[A-Z_][A-Z0-9_]*=/ && !($1 in connues)' \
            "$fichier" "$dossier/.env.example" >> "$brouillon"
    else
        cp "$dossier/.env.example" "$brouillon"
    fi

    for cle in "${!GENERATEURS[@]}"; do
        case "$(valeur "$brouillon" "$cle")" in
            "" | change_me) poser "$brouillon" "$cle" "$("${GENERATEURS[$cle]}")"; ajoutees+=" $cle" ;;
        esac
    done

    declare -A adressage=(
        [PUBLIC_HOST]="$hote" [PUBLIC_ORIGIN]="https://$hote" [COMPOSE_PROJECT_NAME]="enervision-$env"
        [PROXY_HTTPS_PORT]="$port_https" [PROXY_HTTP_PORT]="$port_http" [PROXY_FRONT_PORT]="$port_front"
        [POSTGRES_PORT]="$port_pg" [MAILPIT_UI_PORT]="$port_mailpit" [AIRFLOW_PORT]="$port_airflow"
        [COMPOSE_PROFILES]="$profils" [GRAFANA_PORT]="$port_grafana"
        [PROMETHEUS_PORT]="$port_prometheus" [ALERTMANAGER_PORT]="$port_alertmanager"
        [GARAGE_S3_PORT]="$port_garage_s3" [GARAGE_ADMIN_PORT]="$port_garage_admin"
    )
    for cle in "${!adressage[@]}"; do
        poser "$brouillon" "$cle" "${adressage[$cle]}"
    done

    # Piège : une clé renommée en amont garde sa valeur d'exemple, que le `:?` du compose ne voit
    # pas puisqu'elle n'est pas vide. Cas vécu : AIRFLOW_WEBSERVER_SECRET_KEY, Airflow 3.
    oubliees="$(grep '=change_me$' "$brouillon" | grep -v '^APP_MOCK_API_' | cut -d= -f1 | tr '\n' ' ' || true)"
    if [[ -n "$oubliees" ]]; then
        rm -f "$brouillon"
        erreur "$env : clés sans générateur, .env inchangé : $oubliees"
    fi
    chmod 600 "$brouillon"
    if [[ -f "$fichier" ]]; then
        cat "$brouillon" > "$fichier"
        rm -f "$brouillon"
        echo "$env : .env réaligné sur le tableau${ajoutees:+, secrets ajoutés :$ajoutees}"
    else
        mv "$brouillon" "$fichier"
        echo "$env : .env généré. Reste à renseigner APP_MOCK_API_USERNAME et APP_MOCK_API_PASSWORD."
    fi
    umask "$masque"

    if ! openssl x509 -in "$dossier/infra/proxy/tls/fullchain.pem" -noout -checkhost "$hote" 2>/dev/null \
        | grep -q " does match"; then
        (cd "$dossier" && PUBLIC_HOST="$hote" PUBLIC_IP="$ADRESSE" ./scripts/tls-selfsigned.sh --force)
    fi
    if [[ -r "$JETON_DNS" && "$hote" != *.local ]]; then
        make -C "$dossier" --no-print-directory tls-dns01 PUBLIC_HOST="$hote" \
            || echo "$env : pas de certificat Let's Encrypt, l'auto-signé reste en place" >&2
    fi
    echo "$env : $dossier sur $branche, https://$hote"
}

# Pourquoi : dynv6 est le fournisseur que le filtrage de l'école laisse passer (ADR 0018). Le
# jeton passe par l'environnement du seul processus Python, jamais par `argv`.
publier_dns() {
    [[ -r "$JETON_DNS" ]] || { echo "pas de jeton $JETON_DNS : ni DNS ni Let's Encrypt"; return 0; }
    DNS_TOKEN="$(tr -d '[:space:]' < "$JETON_DNS")" python3 - "$DOMAINE" "$ADRESSE" prod rec dev <<'PY' \
        || echo "DNS : dynv6 refuse la mise à jour de $DOMAINE, enregistrements inchangés" >&2
import json, os, sys, time, urllib.request

domaine, adresse, *sous_noms = sys.argv[1:]

def appel(methode, chemin, corps=None):
    requete = urllib.request.Request(
        f"https://dynv6.com/api/v2/{chemin}", method=methode,
        data=None if corps is None else json.dumps(corps).encode(),
        headers={"Authorization": f"Bearer {os.environ['DNS_TOKEN']}", "User-Agent": "enervision-provision",
                 "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        contenu = reponse.read()
    return json.loads(contenu) if contenu else None

def synchroniser():
    zone = appel("GET", f"zones/by-name/{domaine}")
    if zone.get("ipv4address") != adresse:
        appel("PATCH", f"zones/{zone['id']}", {"ipv4address": adresse})
    existants = {(r["type"], r["name"]): r for r in appel("GET", f"zones/{zone['id']}/records")}
    for nom in sous_noms:
        actuel = existants.get(("A", nom))
        if actuel is None:
            appel("POST", f"zones/{zone['id']}/records", {"type": "A", "name": nom, "data": adresse})
        elif actuel["data"] != adresse:
            appel("PATCH", f"zones/{zone['id']}/records/{actuel['id']}", {"data": adresse})

# dynv6 laisse parfois une écriture sans réponse, appliquée ou non : chaque essai relit l'état
# avant d'écrire, si bien qu'une création aboutie malgré le délai n'est jamais dupliquée.
for essai in range(3):
    try:
        synchroniser()
        break
    except OSError:
        if essai == 2:
            raise
        time.sleep(5)
print(f"DNS : {domaine}, {', '.join(sous_noms)} visent {adresse}")
PY
}

planifier_renouvellement() {
    [[ "$(id -u)" -eq 0 && -n "$PROPRIETAIRE" && -d /etc/cron.d ]] || return 0
    cat > /etc/cron.d/enervision-tls <<CRON
# Renouvellement Let's Encrypt des trois environnements (ADR 0018), écrit par provision-host.sh.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
23 4 * * * $PROPRIETAIRE for e in prod rec dev; do make -C $RACINE/\$e --no-print-directory tls-dns01; done 2>&1 | logger -t enervision-tls
CRON
    chmod 644 /etc/cron.d/enervision-tls
    echo "renouvellement planifié : /etc/cron.d/enervision-tls"
}

verifier_outils
mkdir -p "$RACINE"
publier_dns

# Supervision active en prod seulement (ADR 0016). La prod vit sur `prod.` et non à la racine :
# dynv6 ne sert pas de façon fiable un TXT `_acme-challenge` à la racine de la zone (ADR 0018).
#        env   branche  hôte            https            http             front            pg    mailpit airflow profils    grafana prometheus alertmanager garage-s3 garage-admin
preparer prod  main     "prod.$DOMAINE" 127.0.0.1:10443  127.0.0.1:10080  127.0.0.1:10444  5433  8025    8080    monitoring 3001    9090       9093         3900      3903
preparer rec   dev      "rec.$DOMAINE"  127.0.0.1:8443   127.0.0.1:8081   127.0.0.1:8444   5434  8026    8082    ""         3002    9091       9094         3910      3913
preparer dev   dev      "dev.$DOMAINE"  127.0.0.1:9443   127.0.0.1:8083   127.0.0.1:9444   5435  8027    8084    ""         3003    9092       9095         3920      3923

planifier_renouvellement
if [[ -n "$PROPRIETAIRE" && "$(id -u)" -eq 0 ]]; then
    chown -R "$PROPRIETAIRE" "$RACINE"
fi

cat <<FIN

Démarrage, dans chaque dossier : make stack-up, qui applique aussi les migrations. Puis, une
fois, depuis $RACINE/prod : make front-up, que chaque déploiement de la prod rejoue ensuite.
Premier administrateur, stack démarrée, dans chaque dossier :
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \\
      python -m app.cli create-admin --email <adresse>
Le runner GitHub Actions (label eni-g3) rejouera le déploiement à chaque push sur dev et main,
et déploiera dans dev toute autre branche lancée à la main depuis l'onglet Actions.
L'installer sous le propriétaire de $RACINE, sinon git refuse ces dépôts et le .env en 600 lui
échappe : relancer au besoin ce script avec PROPRIETAIRE=<utilisateur du runner>.
Données historiques : git ne porte pas data/raw, déposer les fichiers dans chaque dossier avant
de déclencher le DAG historical_import.
Noms et certificats : le jeton dynv6 de la zone $DOMAINE doit se trouver dans $JETON_DNS (600,
propriétaire du runner). Sans lui, ni enregistrement DNS ni Let's Encrypt : auto-signé.
FIN
