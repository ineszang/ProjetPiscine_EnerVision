# Point d'avancement · ProjetPiscine_EnerVision · 2026-09-18

Rendu final : **vendredi 25 septembre (J10)**, 9h00 pour le ZIP des livrables et le support EC02.
Source : issues et PR GitHub du repo, branche `dev`. Relevé du 18/09 au matin.

## 1. Ce qui a bougé depuis le point d'hier

Grosse journée : **10 issues fermées**, **8 PR mergées sur `dev`**, **41 commits**.

| Auteur | Commits sur `dev` le 17/09 | Ce qui est arrivé |
|---|---|---|
| **Johan** | 27 | Design système front (#91), politique de mot de passe + mot de passe oublié (#87), vue liste des sites (#49), `GET /sensors/status` (#32), pipeline CI lint+tests (#20, avec Ines) |
| **Meryem** | 6 | Pipeline d'import des données historiques, **#14 fermée** (elle bloquait #15 et #16) |
| **Dorian (phyri0s)** | 3 | `GET /readings` avec fenêtre bornée et pagination, **pipeline d'entraînement LightGBM** posé (#92, ADR 0005) |
| **Valentin** | 4 | Auth frontend mergée (#7), Dependabot (#40), audit de sécu des dépendances en CI |
| **Ines** | 1 | Merge du pipeline CI, config SonarQube |

Le choix ML (#89) a été acté et fermé par tout le monde : **LightGBM, un modèle global**, documenté
dans `docs/adr/0005-modele-prediction-lightgbm.md`. Le module `ml/` existe sur `dev` avec
`data.py`, `features.py`, `train.py`, `baseline.py`, `metrics.py` et 4 fichiers de tests.

Décompte global : **33 issues fermées sur 65** (hier : 25/59). 6 issues créées dans la journée,
32 encore ouvertes, dont **22 sans personne dessus** (hier : 27).

## 2. Où en est chacun

| Membre | Issues ouvertes assignées | Détail |
|---|---|---|
| **Johan** | #19, #29, #51, #61 | Reverse proxy Nginx+TLS · endpoint `current` (PR #84 ouverte depuis le 16/09) · vue détail d'un site (PR #103, CI verte) · tests d'accès rôles |
| **ValentinDeFaria** | #53, #96, #97 | Vue supervision des capteurs (prise hier) · audit dépendances CI (PR #100) · couverture tests front CI (PR #101) |
| **phyri0s (Dorian)** | #5, #30 | Jeu de données d'entraînement simulé · #30 `/readings` **est livrée (PR #94 mergée) mais l'issue n'a pas été fermée** |
| **ineszang** | #21 | Pipeline CD (déploiement SSH) · PR #99 SonarQube approuvée mais check en échec |
| **Meryemel-gham** | **aucune** | #14 fermée hier à 10h11, rien de repris depuis |
| **Non assigné** | **22 issues** | Voir sections 4 et 5 |

## 3. Avancement par jalon

| Jalon | Échéance | Fermées / total | Hier | Statut |
|---|---|---|---|---|
| J1 - Environnement & repo | 14/09 | 5/5 | 5/5 | ✅ |
| J2 - Périmètre & choix techos | 15/09 | 4/4 | 4/4 | ✅ |
| **J3 - Ingestion & backend** | **18/09 (aujourd'hui)** | 9/15 | 6/12 | 🔴 60 %, **échoit ce soir avec 6 ouvertes** |
| **J4 - Architecture, sécurité, frontend** | **21/09 (J+3)** | 10/30 | 6/26 | 🔴 33 %, 20 ouvertes |
| **J5 - Robustesse & livrables** | **23/09 (J+5)** | 1/5 | 0/5 | 🔴 20 %, 4 ouvertes, **0 assignée** |

La journée d'hier a fait gagner 10 points sur J3 et 10 sur J4, mais le périmètre a aussi grossi
(59 → 65 issues). **Le retard identifié hier n'est pas résorbé, il est stabilisé.**

## 4. J3 échoit aujourd'hui : les 6 issues restantes

| Issue | Qui | État réel |
|---|---|---|
| #5 Jeu de données d'entraînement simulé | Dorian | En cours, socle posé hier |
| **#6 Entraîner le modèle** | **personne** | Le pipeline existe (#92), il manque le porteur de l'entraînement effectif |
| **#15 DAG Airflow - normalisation** | **personne** | **Débloquée hier** par la fermeture de #14 |
| **#16 DAG Airflow - chargement micro-batch** | **personne** | **Débloquée hier** par la fermeture de #14 |
| #44 Tests unitaires modèle/recommandations | **personne** | Dépend de #6 |
| #61 Tests d'accès API sécurisée (rôles) | Johan | **Débloquée** : les endpoints métier qui manquaient (#28, #32, #33, #59, #60) sont livrés |

Quatre de ces six n'ont personne dessus, dont les deux DAG Airflow qui viennent tout juste d'être
débloqués. **Meryem, qui a écrit l'ingestion (#14), n'a plus d'issue assignée** : c'est le
rapprochement le plus évident à faire ce matin.

## 5. À décider ensemble ce matin

1. **`main` est figée au 14/09.** `dev` a **161 commits d'avance** et rien n'a jamais été remonté.
   Le rendu du 25/09 se fait sur le Git : il faut décider maintenant qui merge `dev` → `main`,
   quand, et si on le fait en continu ou en une fois à la fin. Une remontée de 161 commits la
   veille du rendu est le risque le plus concret du projet aujourd'hui.

2. **Affecter les 4 issues J3 orphelines aujourd'hui** : #6 (entraînement du modèle), #15 et #16
   (DAG Airflow, débloqués), #44 (tests ML). Proposition : #15/#16 à Meryem (continuité de #14),
   #6 à Dorian en suite de #5.

3. **Purger la file de PR : 5 ouvertes, dont une depuis le 16/09.**

   | PR | Auteur | CI | Ce qui bloque |
   |---|---|---|---|
   | #84 `sites/{id}/current` | Johan | verte | **ouverte depuis le 16/09**, rien ne la retient |
   | #103 vue détail d'un site | Johan | verte sauf SonarCloud | vérification visuelle |
   | #101 couverture tests front | Valentin | **entièrement verte** | personne n'a reviewé |
   | #100 audit dépendances CI | Valentin | verte sauf SonarCloud | personne n'a reviewé |
   | #99 config SonarQube | Ines | **SonarQube en échec** | approuvée, mais le check rouge |

   SonarCloud est en échec sur #103 et #100, SonarQube sur #99. On avait acté hier que
   « SonarCloud non-bloquant = go de merge ». **Soit on applique cette règle pour de bon et on
   merge, soit Ines finit #99 et on redevient strict.** Rester entre les deux fait que rien ne part.

4. **J5 n'a aucun assigné à 5 jours de l'échéance** : #41 (DAST OWASP ZAP), #45 (tests
   d'intégration API↔DB↔ML), #46 (E2E Playwright), #47 (tests de charge k6). Ce sont exactement
   les livrables qui servent de preuve à EC03 et EC04. À nommer aujourd'hui, même sans démarrer.

5. **Hygiène de suivi** : #30 est livrée (PR #94 mergée hier) mais son issue est ouverte, et #29
   attend juste le merge de #84. Deux issues qui font croire à du reste à faire. À fermer.

6. **J4 : 20 ouvertes pour lundi.** Le front concentre le volume (#9 widget alerte de pic, #10 vue
   recommandations, #11 responsive, #54 comparateur de scénarios), plus le ML applicatif (#37
   service de scoring, #38 moteur de règles) et l'infra (#22 secrets, #24 MinIO, #26 monitoring,
   #36 rétention, #42 chiffrement au repos, #43 accessibilité). Hier il a été acté de **ne rien
   couper**. À 3 jours de l'échéance et 5 personnes, ce choix se reconfirme ou se révise ce matin,
   avec les chiffres sous les yeux.

## 6. Ce qui va bien, et qu'il faut garder

- Le rythme du 17/09 (10 issues fermées, 8 PR mergées) est le bon rythme. Tenu 5 jours, il vide
  la file.
- La chaîne de revue fonctionne : Dorian a reviewé #93 et #95, les remarques ont été traitées
  avant merge.
- Le backend est essentiellement là : auth + RBAC + audit, `/sites`, `/readings`, `/stats/summary`,
  `/alerts`, `/recommendations`, `/sensors/status`, contrat OpenAPI versionné, import historique.
  Le reste du projet s'appuie dessus, et ce socle ne bougera plus.
- 5 ADR écrits et à jour : c'est de la matière directement réutilisable pour EC01 et EC02.
