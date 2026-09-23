# 0015 - Les tests de bout en bout et de charge visent la stack Compose déployée

- Statut : accepté
- Date : 2026-09-23

## Contexte

Les issues #46 (Playwright) et #47 (k6) demandent des preuves de robustesse pour EC03 et EC04.
Rien ne vérifiait un parcours utilisateur complet : les tests du frontend simulent l'API, ceux
du backend n'ouvrent pas de navigateur. Rien ne mesurait non plus l'API sous charge, et le
dépôt ne chiffre aucun temps de réponse ni aucun volume d'utilisateurs.

Trois contraintes du système pèsent sur la manière de tester :

- **La session tient dans un cookie de refresh HttpOnly qui tourne à chaque usage.** Rejouer un
  cookie déjà servi révoque toute la famille de session (ADR 0002).
- **Le cookie n'est `__Secure-` et `Secure` que hors `local`, derrière le proxy TLS.** Tester
  contre `ng serve` ne dit rien de ce que voit un navigateur en prod (ADR 0007).
- **nginx limite chaque adresse IP** à 20 req/s sur l'API, avec une rafale de 40, et à 30
  connexions par minute, avec une rafale de 20 (ADR 0007). Tout le trafic d'un tir parti d'une
  seule machine partage la même adresse.

## Décision

**Playwright joue contre la stack de prod** (`docker-compose.yml` et
`docker-compose.prod.yml`), sur `https://localhost` avec un certificat auto-signé.
- **En CI**, le workflow `e2e.yml` démarre `db`, `mailpit`, `backend`, `frontend` et `proxy`,
  sème `db/seeds/demo.sql` et crée les comptes par `scripts/comptes-test.sh`.
- **Sur le poste**, la même suite vise `make dev` (`http://localhost:4200`).
- **Écriture des tests**, imposée par la rotation du refresh et par la zone `auth` :
  - un seul worker ;
  - une session par fichier, sans `storageState` partagé ;
  - chaque parcours qui consomme un compte le crée lui-même.

**k6 tourne en service Compose (profil `load`) sur le réseau du projet et vise `backend:8000`**,
pour mesurer l'API et non la limite de nginx. Un seul scénario, `limitation-debit.js`, passe par
`https://proxy`, pour vérifier que la limite tient : des 429, jamais de 5xx.

**Hypothèses et seuils**, faute d'exigence chiffrée :

| Hypothèse ou seuil | Valeur |
|---|---|
| Utilisateurs simultanés | 50 : 40 sur le tableau de bord, qui interroge `/stats/summary` toutes les 10 s et `/alerts` toutes les 60 s ; 10 qui explorent les sites |
| Lectures, p95 | < 500 ms |
| Lectures, p99 | < 1 s |
| Échecs HTTP | < 1 % |
| Vérifications réussies | > 99 % |

**En CI de PR** : Playwright, le tir `smoke` (une minute) et `limitation-debit`. La charge
nominale et le stress se lancent à la main (`make load-test`, `make load-stress`), en recette,
parce que rec et prod partagent la VM (ADR 0009).

## Alternatives écartées

| Écartée | Raison |
|---|---|
| Playwright contre `ng serve` en CI | Pas de TLS, pas de cookie `__Secure-`, pas de CSP ni de limitation : le parcours testé ne serait pas celui des utilisateurs. |
| `storageState` partagé entre fichiers | Chaque fichier rejouerait le même cookie de refresh ; le second usage révoque la famille, et la suite échoue de façon intermittente selon l'ordre. |
| k6 depuis le runner, à travers le proxy | Au-delà de 20 req/s, on mesure nginx. Relever la limite pour le tir, ce serait tester une configuration qui n'est pas celle de la prod. |
| Tir de charge complet à chaque PR | Huit minutes de plus par PR, sur un runner partagé dont les performances varient d'un run à l'autre : un seuil franchi n'y voudrait rien dire. |
| Un workflow k6 en `workflow_dispatch` contre la recette | La recette partage la VM avec la prod ; un tir déclenché d'un clic ralentirait la prod sans que personne soit prévenu. La cible Makefile, lancée sur la VM, garde un humain dans la boucle. |

## Conséquences

- La CI construit enfin les images backend et frontend avant le déploiement, par le job E2E.
- `db/seeds/demo.sql` et `scripts/comptes-test.sh` deviennent le jeu commun de la CI, repris par
  le DAST. Les deux sont réservés aux bases jetables.
- Les seuils de k6 sont des hypothèses de l'équipe : à réviser dès qu'un besoin chiffré existe.
- L'API expose des seaux de latence fins autour de 500 ms, pour que Grafana lise le même seuil
  que k6 (ADR 0016).
