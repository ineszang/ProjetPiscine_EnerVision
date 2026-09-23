#!/usr/bin/env bash
# Pourquoi : la machine porte trois environnements, chacun un clone du dépôt, un `.env` et un
# projet Compose (ADR 0009, ADR 0017). Ce script prépare la machine et les trois dossiers sans
# rien démarrer : construction des images et démarrage restent à l'opérateur, puis au runner.
# Piège : lancé en root, git refuse un clone déjà chowné au runner (propriété douteuse). D'où
# `safe.directory` passé en ligne de commande, seule portée où git l'accepte - preparer().
# Rejouable : un dossier déjà cloné est réaligné sur sa branche, un `.env` existant n'est jamais
# réécrit, un certificat présent n'est jamais régénéré.

set -euo pipefail

DEPOT="${REPO_URL:-https://github.com/ineszang/ProjetPiscine_EnerVision.git}"
RACINE="${RACINE:-/srv/enervision}"
ADRESSE="${PUBLIC_IP:-$(hostname -I | awk '{print $1}')}"
PROPRIETAIRE="${PROPRIETAIRE:-${SUDO_USER:-}}"
COMPOSE_MINIMALE="2.24.4"

erreur() { echo "erreur : $*" >&2; exit 1; }
secret() { openssl rand -base64 48 | tr -d '/+=\n' | cut -c1-48; }
# Clé Fernet : 32 octets en base64 urlsafe, padding compris.
fernet() { openssl rand -base64 32 | tr '+/' '-_'; }

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

preparer() {
    local env="$1" branche="$2" hote="$3" origine="$4"
    local port_https="$5" port_http="$6" port_pg="$7" port_mailpit="$8" port_airflow="$9"
    local profils="${10}" port_grafana="${11}" port_prometheus="${12}" port_alertmanager="${13}"
    local dossier="$RACINE/$env"

    if [[ -d "$dossier/.git" ]]; then
        local git=(git -c "safe.directory=$dossier" -C "$dossier")
        "${git[@]}" fetch --quiet origin "$branche"
        "${git[@]}" checkout --quiet "$branche"
        "${git[@]}" reset --quiet --hard "origin/$branche"
    else
        git clone --quiet --branch "$branche" "$DEPOT" "$dossier"
    fi

    if [[ ! -f "$dossier/.env" ]]; then
        local brouillon="$dossier/.env.brouillon" oubliees
        sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(secret)|" \
            -e "s|^POSTGRES_PORT=.*|POSTGRES_PORT=$port_pg|" \
            -e "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$(secret)|" \
            -e "s|^MAILPIT_UI_PORT=.*|MAILPIT_UI_PORT=$port_mailpit|" \
            -e "s|^AIRFLOW_PORT=.*|AIRFLOW_PORT=$port_airflow|" \
            -e "s|^AIRFLOW_FERNET_KEY=.*|AIRFLOW_FERNET_KEY=$(fernet)|" \
            -e "s|^AIRFLOW_API_SECRET_KEY=.*|AIRFLOW_API_SECRET_KEY=$(secret)|" \
            -e "s|^AIRFLOW_JWT_SECRET=.*|AIRFLOW_JWT_SECRET=$(secret)|" \
            -e "s|^AIRFLOW_ADMIN_PASSWORD=.*|AIRFLOW_ADMIN_PASSWORD=$(secret | cut -c1-20)|" \
            -e "s|^AIRFLOW_APP_SECRET_KEY=.*|AIRFLOW_APP_SECRET_KEY=$(secret)|" \
            -e "s|^PUBLIC_HOST=.*|PUBLIC_HOST=$hote|" \
            -e "s|^PUBLIC_ORIGIN=.*|PUBLIC_ORIGIN=$origine|" \
            -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=enervision-$env|" \
            -e "s|^PROXY_HTTP_PORT=.*|PROXY_HTTP_PORT=$port_http|" \
            -e "s|^PROXY_HTTPS_PORT=.*|PROXY_HTTPS_PORT=$port_https|" \
            -e "s|^COMPOSE_PROFILES=.*|COMPOSE_PROFILES=$profils|" \
            -e "s|^APP_METRICS_TOKEN=.*|APP_METRICS_TOKEN=$(secret)|" \
            -e "s|^GRAFANA_ADMIN_PASSWORD=.*|GRAFANA_ADMIN_PASSWORD=$(secret | cut -c1-20)|" \
            -e "s|^SUPERVISION_DB_PASSWORD=.*|SUPERVISION_DB_PASSWORD=$(secret)|" \
            -e "s|^GRAFANA_PORT=.*|GRAFANA_PORT=$port_grafana|" \
            -e "s|^PROMETHEUS_PORT=.*|PROMETHEUS_PORT=$port_prometheus|" \
            -e "s|^ALERTMANAGER_PORT=.*|ALERTMANAGER_PORT=$port_alertmanager|" \
            "$dossier/.env.example" > "$brouillon"
        # Branche antérieure à l'ADR 0009 : ces clés manquent alors dans .env.example.
        for cle in "COMPOSE_PROJECT_NAME=enervision-$env" "PUBLIC_ORIGIN=$origine" \
                   "PROXY_HTTP_PORT=$port_http" "PROXY_HTTPS_PORT=$port_https"; do
            grep -q "^${cle%%=*}=" "$brouillon" || echo "$cle" >> "$brouillon"
        done
        # Piège : une clé renommée en amont garde sa valeur d'exemple, que le `:?` du compose ne
        # voit pas puisqu'elle n'est pas vide. Cas vécu : AIRFLOW_WEBSERVER_SECRET_KEY, Airflow 3.
        oubliees="$(grep '=change_me$' "$brouillon" | grep -v '^APP_MOCK_API_' | cut -d= -f1 | tr '\n' ' ' || true)"
        if [[ -n "$oubliees" ]]; then
            rm -f "$brouillon"
            erreur "$env : secrets non générés, .env non écrit : $oubliees"
        fi
        chmod 600 "$brouillon"
        mv "$brouillon" "$dossier/.env"
        echo "$env : .env généré. Reste à renseigner APP_MOCK_API_USERNAME et APP_MOCK_API_PASSWORD."
    fi

    if [[ ! -f "$dossier/infra/proxy/tls/fullchain.pem" ]]; then
        (cd "$dossier" && PUBLIC_HOST="$hote" PUBLIC_IP="$ADRESSE" ./scripts/tls-selfsigned.sh)
    fi
    echo "$env : $dossier sur $branche, $origine"
}

verifier_outils
mkdir -p "$RACINE"

# Supervision active en prod seulement (ADR 0016) ; les ports de la recette et de dev restent
# décalés au cas où on l'y lancerait à la demande.
#        env   branche  hôte                  origine                            https  http            pg    mailpit airflow profils    grafana prometheus alertmanager
preparer prod  main     enervision.local      https://enervision.local           443    80              5433  8025    8080    monitoring 3001    9090       9093
preparer rec   dev      rec.enervision.local  https://rec.enervision.local:8443  8443   127.0.0.1:8081  5434  8026    8082    ""         3002    9091       9094
preparer dev   dev      dev.enervision.local  https://dev.enervision.local:9443  9443   127.0.0.1:8083  5435  8027    8084    ""         3003    9092       9095

if [[ -n "$PROPRIETAIRE" && "$(id -u)" -eq 0 ]]; then
    chown -R "$PROPRIETAIRE" "$RACINE"
fi

cat <<FIN

Démarrage, dans chaque dossier : make stack-up, qui applique aussi les migrations.
Premier administrateur, stack démarrée, dans chaque dossier :
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \\
      python -m app.cli create-admin --email <adresse>
Le runner GitHub Actions (label eni-g3) rejouera le déploiement à chaque push sur dev et main,
et déploiera dans dev toute autre branche lancée à la main depuis l'onglet Actions.
L'installer sous le propriétaire de $RACINE, sinon git refuse ces dépôts et le .env en 600 lui
échappe : relancer au besoin ce script avec PROPRIETAIRE=<utilisateur du runner>.
Données historiques : git ne porte pas data/raw, déposer les fichiers dans chaque dossier avant
de déclencher le DAG historical_import.
Depuis un poste : ajouter « $ADRESSE enervision.local rec.enervision.local dev.enervision.local »
à /etc/hosts.
FIN
