# 0018 - Noms publics, certificats Let's Encrypt par DNS-01 et frontal SNI sans port

- Statut : accepté
- Date : 2026-09-23

## Contexte

Les trois environnements de la VM ENI ([ADR 0009](0009-deux-environnements-compose-sur-la-vm-eni.md),
[ADR 0017](0017-environnement-dev-a-la-demande.md)) répondaient sur `enervision.local`,
`rec.enervision.local:8443` et `dev.enervision.local:9443`, avec des certificats auto-signés.
Chaque poste devait éditer son `/etc/hosts` et accepter trois avertissements du navigateur :
rien de présentable à un jury, et rien d'utilisable par quelqu'un qui n'a pas la main sur son
poste.

Contraintes : la VM n'a qu'une IP privée, `10.101.200.37`, que ni Internet ni Let's Encrypt ne
joignent, et le réseau de l'école ne doit pas être touché. Vérifications faites le 23/09 : les
résolveurs de l'école rendent bien une adresse privée pour un nom public, la VM sort en HTTPS
vers Let's Encrypt et vers l'API de dynv6, mais le filtrage de l'école bloque duckdns.org, site
et API, depuis les postes comme depuis la VM.

## Décision

**Des noms publics qui visent l'IP privée.** `enervision-g3.dynv6.net`, zone gratuite de dynv6,
porte la prod, et deux enregistrements A portent `rec.` et `dev.`. `provision-host.sh` les publie
par l'API dynv6 : le DNS est décrit par le code comme le reste. Tout
poste du réseau de l'école les résout sans configuration ; hors de ce réseau, l'IP ne mène
nulle part.

**Des certificats Let's Encrypt par défi DNS-01.** Le défi passe par l'API dynv6, qui pose
l'enregistrement TXT : Let's Encrypt n'a jamais à joindre la VM. `make tls-dns01` (acme.sh
épinglé) le joue dans chaque stack ; il ne renouvelle qu'à échéance, d'où son rejeu à chaque
déploiement et chaque nuit par cron. Un certificat par environnement plutôt qu'un joker : chaque
stack garde le sien, et la clé de la prod n'est pas lisible depuis le clone de dev.

**Un frontal SNI sur 443, le seul composant exposé.** `infra/front`, un nginx sur le réseau de
l'hôte, lit le nom demandé dans le ClientHello et relaie le flux TLS intact vers la stack visée,
publiée sur la boucle locale. Il ne détient aucun certificat. Le port 80 y redirige vers
HTTPS. Les URL perdent leur port.

**Le PROXY protocol entre frontal et stacks.** Relayé tel quel, le flux arriverait avec l'IP du
frontal : `limit_req` et `get_client_ip()` compteraient tous les postes comme un seul, et un
utilisateur bloquerait la connexion de tous. Chaque proxy de stack reçoit donc le frontal sur un
écouteur dédié, 4443, qui exige l'en-tête PROXY protocol et en tire l'IP du client. Le 443 de
la stack reste sans PROXY protocol, pour les postes de développement et la sonde du déploiement.

**Le fournisseur est un paramètre.** `DNS01_API` et `DNS01_JETON_VAR` nomment le greffon acme.sh,
le jeton vit dans `dns.token` quel que soit le fournisseur : passer à un domaine acheté chez
Cloudflare ou OVH ne demande que ces deux variables et `domaine`, plus `publier_dns()`.

**`scripts/provision-host.sh` fait foi pour l'adressage et les secrets.** Un `.env` existant
garde ses secrets, reçoit ceux qui lui manquent et voit hôte, ports et profils réalignés sur le
tableau du script. C'est ce qui permet de migrer trois `.env` nés avant ce changement, et le
clone de la prod, en retard sur `main`, sans dépendre de son `.env.example`.

## Alternatives écartées

- **Garder `/etc/hosts` et l'auto-signé** : trois manipulations par poste et trois
  avertissements, précisément ce qu'il fallait supprimer.
- **DuckDNS** : premier choix, inscription en un clic, mais bloqué par le filtrage de l'école :
  sans son API, pas de défi DNS-01.
- **deSEC (`dedyn.io`)** : joignable et associatif, mais les inscriptions de nouveaux domaines
  `dedyn.io` étaient fermées le 23/09 ; il reste le bon choix pour un domaine acheté.
- **nip.io ou sslip.io** : résolution sans compte, mais aucun moyen d'y obtenir un certificat.
- **Services à certificat joker public (traefik.me, local-ip.co)** : leur clé privée est publiée
  par conception, n'importe qui peut usurper ces noms.
- **Tunnel vers Internet (Cloudflare Tunnel, Tailscale Funnel)** : accès depuis l'extérieur,
  mais l'application serait exposée hors de l'école, décision refusée.
- **Autorité de certification interne (mkcert, step-ca)** : chaque poste devrait l'installer.
- **Terminaison TLS au frontal** : un seul endroit pour les certificats, mais les stacks
  recevraient du HTTP clair que leur proxy redirige vers HTTPS, et en-têtes de sécurité comme
  limitation de débit seraient à déplacer. Le relais SNI ne touche à rien de tout cela.
- **Domaine acheté** : plus présentable, mais un achat et un compte de plus pour un bénéfice nul
  sur l'accès. Seule `DOMAINE` changerait.

## Conséquences

- L'objection de l'ADR 0009 à un proxy frontal, qui aurait dû joindre plusieurs réseaux Compose
  aux services homonymes, tombe : le frontal ne joint que des ports de la boucle locale.
- Sans le frontal, plus rien n'est joignable sur la VM. `deploy.yml` le relance à chaque
  déploiement de la prod, et son `restart: unless-stopped` le ramène après un redémarrage.
- Le jeton dynv6 vit dans `/srv/enervision/dns.token`, jamais dans git, GitHub ni le state
  Terraform ; acme.sh en garde une copie dans `infra/proxy/acme/`, retirée à la lecture des
  autres comptes. Qui le détient peut repointer les trois noms.
- dynv6 devient une dépendance : s'il tombe, les noms cessent de résoudre et les
  renouvellements échouent. Les certificats valent 90 jours, la marge est large.
- Un filtrage de l'école qui viendrait à bloquer dynv6 arrêterait les renouvellements, pas les
  noms : la résolution passe par les serveurs DNS de l'école, pas par le site.
- Les noms sont publics mais ne mènent qu'à une IP privée : ils révèlent l'existence de la VM,
  pas son contenu.
