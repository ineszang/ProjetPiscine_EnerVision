# Pourquoi : Terraform provisionne la machine, GitHub Actions la deploie (ADR 0010). Rien ici ne
# construit d'image ni ne lance de conteneur : la livraison reste portee par `deploy.yml` et
# `make stack-up`, et un `apply` n'interrompt pas la stack qui tourne.
# Piege : seul le bloc `triggers` d'un `null_resource` atterrit dans le state. Ni le jeton du
# runner ni la cle SSH n'y figurent, et ne doivent jamais y etre ajoutes pour forcer un rejeu.
# Contrainte : pas de provisioner `destroy` sur le runner. Il imposerait une connexion ne lisant
# que `self`, donc le chemin de la cle SSH dans le state, et `svc.sh uninstall` ne desinscrit pas
# le runner cote GitHub : le retrait reste manuel, depuis les parametres du depot.
# Ref : ADR 0009 et 0017 pour les trois environnements, `scripts/provision-host.sh` pour leur contenu.

locals {
  sudo           = var.ssh_user == "root" ? "" : "sudo "
  en_tant_que    = "${var.ssh_user == "root" ? "" : "sudo "}runuser -u ${var.proprietaire} --"
  provisionneur  = "${path.root}/../../../../scripts/provision-host.sh"
  runner_archive = "actions-runner-linux-x64-${var.runner_version}.tar.gz"
  # Substitution shell, evaluee par le sh -c distant : un nom de runner doit etre unique dans
  # le depot, le nom d'hote l'est deja et le reste si cette racine sert a une autre machine.
  runner_nom = var.runner_nom != "" ? var.runner_nom : "$(hostname -s)"
}

resource "null_resource" "docker_engine" {
  triggers = {
    hote = var.ssh_host
    user = var.proprietaire
  }

  connection {
    type        = "ssh"
    host        = var.ssh_host
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(pathexpand(var.ssh_private_key_path))
    timeout     = "5m"
  }

  provisioner "remote-exec" {
    inline = [
      <<-EOT
        set -eu
        id ${var.proprietaire} >/dev/null 2>&1 || {
          echo "l'utilisateur ${var.proprietaire} n'existe pas sur la machine" >&2
          exit 1
        }
        command -v docker >/dev/null || ${local.sudo}sh -c 'curl -fsSL https://get.docker.com | sh'
        ${local.sudo}systemctl enable --now docker
        ${local.sudo}usermod -aG docker ${var.proprietaire}
        ${local.sudo}docker compose version
      EOT
    ]
  }
}

# `provision-host.sh` verifie lui-meme docker, compose et la sortie HTTPS, puis prepare un clone
# par environnement, son `.env` et son certificat. Il est rejouable : un `.env` existant n'est
# jamais reecrit, un certificat present jamais regenere.
resource "null_resource" "environnements" {
  depends_on = [null_resource.docker_engine]

  triggers = {
    script = filesha256(local.provisionneur)
    racine = var.racine
    depot  = var.depot_url
  }

  connection {
    type        = "ssh"
    host        = var.ssh_host
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(pathexpand(var.ssh_private_key_path))
    timeout     = "5m"
  }

  provisioner "file" {
    source      = local.provisionneur
    destination = "/tmp/provision-host.sh"
  }

  provisioner "remote-exec" {
    inline = [
      <<-EOT
        set -eu
        ${local.sudo}env RACINE='${var.racine}' \
          REPO_URL='${var.depot_url}' \
          PROPRIETAIRE='${var.proprietaire}' \
          PUBLIC_IP='${var.adresse_publique}' \
          bash /tmp/provision-host.sh
        rm -f /tmp/provision-host.sh
      EOT
    ]
  }
}

# Piege : le jeton d'enregistrement expire en une heure. Un `apply` rejoue cette ressource des
# que `runner_version`, `runner_labels` ou `runner_nom` change, et redemande donc un jeton frais.
resource "null_resource" "runner_github" {
  depends_on = [null_resource.environnements]

  triggers = {
    version = var.runner_version
    labels  = var.runner_labels
    nom     = local.runner_nom
    dossier = var.runner_dossier
  }

  connection {
    type        = "ssh"
    host        = var.ssh_host
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(pathexpand(var.ssh_private_key_path))
    timeout     = "5m"
  }

  provisioner "remote-exec" {
    inline = [
      <<-EOT
        set -eu
        ${local.sudo}install -d -o ${var.proprietaire} -g ${var.proprietaire} ${var.runner_dossier}
        if [ ! -x ${var.runner_dossier}/config.sh ]; then
          curl -fsSL -o /tmp/${local.runner_archive} \
            https://github.com/actions/runner/releases/download/v${var.runner_version}/${local.runner_archive}
          ${local.sudo}tar -xzf /tmp/${local.runner_archive} -C ${var.runner_dossier}
          ${local.sudo}chown -R ${var.proprietaire}:${var.proprietaire} ${var.runner_dossier}
          rm -f /tmp/${local.runner_archive}
        fi
        if [ ! -f ${var.runner_dossier}/.runner ]; then
          ${local.en_tant_que} sh -c 'cd ${var.runner_dossier} && ./config.sh --unattended --replace \
            --url ${var.runner_url} --token ${var.runner_token} \
            --labels ${var.runner_labels} --name ${local.runner_nom} --work _work'
          ${local.sudo}${var.runner_dossier}/svc.sh install ${var.proprietaire}
        fi
        ${local.sudo}${var.runner_dossier}/svc.sh start
      EOT
    ]
  }
}
