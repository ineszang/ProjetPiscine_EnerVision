# EC02 · Management de projet : rapport collectif

**Groupe 3 (HEADL_015B) · Projet EnerVision.**

| | |
|---|---|
| **Fichier source** | `EADL26_EC02 - Rapport Collectif HEADL_015B-G3.md`, encodage UTF-8, aucun média externe |
| **Version figée** | `EADL26_EC02 - Rapport Collectif HEADL_015B-G3.pdf`, produite par la chaîne Markdown → HTML → CSS de pagination → PDF |
| **Dépôt** | Devoir Teams, à côté du ZIP du dépôt Git, **et** dans le dépôt Git lui-même (`docs/livrables/EC02/`) |
| **Échéance** | Vendredi 25/09/2026, 9h00 (gel technique) |
| **Relevé** | **24/09/2026 à 14h25**, sur le commit gelé `9f343e9` (`dev` = `main`) et par l'API GitHub : dépôt, tracker, board, jalons, PR et revues relevés au même instant, heures en heure locale (CEST) |

Chaque chiffre de ce rapport est reproductible par une commande citée en fin de document : le
critère officiel est un compte rendu d'activité « complet et **honnête** ». Les chiffres du
rapport du 23/09 (board du 18/09, tracker du 21/09) sont remplacés, pas complétés.

---

## 1. Organisation de l'équipe

Le pilotage passe par un **GitHub Project** (« EnerVision », projet n°2), avec assignation
nominative, et par le dépôt `ProjetPiscine_EnerVision`, branche d'intégration `dev`, branche de
production `main`.

### Activité par membre

| Membre | Compte GitHub | Commits sur `dev`, hors merges | PR mergées, auteur principal | PR mergées par lui | Board : Done / En cours / Todo | Domaines observés dans ses PR |
|---|---|---|---|---|---|---|
| Johan LEROY | `JohanLeroy` | 172 | 34 | 59 | 36 / 0 / 0 | Socle backend et sécurité, moteur de règles, vues frontend, déploiement et environnements, CI, supervision, stockage objet |
| Dorian PESCE | `phyri0s` | 42 | 11 | 11 | 16 / 0 / 0 | Terraform k3s, endpoints, pipeline LightGBM, scoring, alertes internes, DAGs ML, DAST, en-tête CORP, réconciliation des sources |
| Inès ZANG | `ineszang` | 54 | 4 | 5 | 5 / 2 / 0 | Terraform initial, pipeline CI, SonarCloud, administration du dépôt, procédures de déploiement |
| Meryem EL GHAM | `Meryemel-gham` | 23 | 6 | 2 | 7 / 2 / 0 | Schéma de données, imports historique et API Mock, DAGs d'import |
| Valentin DE FARIA RODRIGUES | `ValentinDeFaria` | 20 | 8 | 4 | 12 / 0 / 0 | Frontend et ses tests, auth frontend, audit de dépendances, supervision des capteurs, registre MLflow, amorce Garage |
| Dependabot | - | 12 | 12 | - | - | Mises à jour de dépendances |
| *(remontées `dev` → `main`)* | - | - | 6 | - | - | - |
| *(non assigné)* | - | - | - | - | 1 / 0 / 1 | - |

Totaux : **323 commits** hors merges sur `dev` (458 avec merges), **81 PR mergées**, 69 éléments
au board. Méthode : l'**auteur principal** d'une PR est l'auteur majoritaire des commits de sa
branche, qui peut différer du membre qui l'a ouverte. Les six remontées de `dev` vers `main` ne sont attribuées à
personne. Le nombre de commits mesure une activité, pas une valeur : les pratiques de découpage
diffèrent d'un membre à l'autre.

**Correspondances nom / identifiant.** Établies par Git : `Dorian`, `Dorian PESCE` et
`Phyrios` sont le compte `phyri0s` ; `ineszang` et `ineszang44` partagent la même adresse,
`Valentin` et `valentin` aussi.

**Rôles principaux** (Tech Lead, Cloud/DevOps, Data & IA, Fullstack Dev, PO). Seul celui de
Tech Lead a été nommé au départ ; les autres se lisent dans les PR de chacun :

| Membre | Rôle principal exercé |
|---|---|
| Johan LEROY | **Tech Lead** : architecture, intégration, sécurité, déploiement |
| Dorian PESCE | **Data & IA** : modèle LightGBM, DAGs ML, scoring, scan DAST |
| Inès ZANG | **Cloud / DevOps** : Terraform initial, pipeline CI, SonarCloud, administration du dépôt |
| Meryem EL GHAM | **Data** : schéma de données, imports historique et API Mock, DAGs d'import |
| Valentin DE FARIA RODRIGUES | **Fullstack Dev** : frontend et ses tests, supervision des capteurs, registre MLflow |

Le rôle de **PO** n'a pas eu de titulaire nommé : les arbitrages de périmètre ont été pris aux
points d'avancement, dont la coupe du 21/09. Le formateur demandait une **rotation** des rôles
sur les deux semaines : elle n'a pas eu lieu. Chacun est resté sur son domaine d'origine, ce qui a
favorisé la vitesse au détriment de la polyvalence.

### RACI

Reconstitué depuis l'historique des PR mergées, chaque PR étant rattachée aux chantiers dont elle
touche les fichiers : *Responsible* = qui écrit, *Accountable* = qui valide le merge,
*Consulted* = qui relit (revue ou commentaire), *Informed* = toute l'équipe, par le board et les
points d'avancement.

| Chantier | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Backend / API | les cinq membres | `ineszang`, `JohanLeroy`, `Meryemel-gham`, `phyri0s` | `JohanLeroy`, `Meryemel-gham`, `phyri0s`, `ValentinDeFaria` | équipe |
| Frontend | `ineszang`, `JohanLeroy`, `phyri0s`, `ValentinDeFaria` | `ineszang`, `JohanLeroy`, `phyri0s`, `ValentinDeFaria` | `JohanLeroy`, `Meryemel-gham`, `phyri0s` | équipe |
| Data & ML | `JohanLeroy`, `Meryemel-gham`, `phyri0s`, `ValentinDeFaria` | les cinq membres | `JohanLeroy`, `phyri0s` | équipe |
| Infra / CI-CD | les cinq membres | les cinq membres | `JohanLeroy`, `Meryemel-gham`, `phyri0s` | équipe |
| Sécurité | `JohanLeroy`, `Meryemel-gham`, `phyri0s`, `ValentinDeFaria` | `JohanLeroy`, `phyri0s` | `JohanLeroy`, `Meryemel-gham`, `phyri0s` | équipe |

Membres cités par ordre alphabétique de leur compte. Lecture : chaque chantier compte au moins
quatre contributeurs, plusieurs membres ont validé des merges sur chacun, et chacun a été relu
par au moins deux membres. Le RACI n'a pas été posé en amont : il est reconstitué depuis les
merges et les revues.

---

## 2. Méthodologie, backlog, user stories

Constat factuel tiré du GitHub Project, du tracker d'issues et du dépôt :

- **Méthodologie** : **Kanban à jalons**, pratiqué sans avoir été nommé en amont. Le board a
  **3 colonnes** (`Todo` / `In progress` / `Done`), découpé en **2 itérations** (« Première
  semaine », « Seconde semaine ») et **6 jalons datés**.
- **Priorisation MoSCoW** appliquée à chaque ticket, et **respectée dans les faits** : au
  24/09, **56 `Must` faits sur 56**, 5 `Should` sur 5, 4 `Could` sur 6. Au 18/09, 66 % des
  `Must` étaient faits contre 0 % des `Should` et des `Could` : aucun ticket de confort n'a été
  pris avant un ticket essentiel.
- **Estimation en taille de tee-shirt** : 48 S, 13 M, 5 XS, 3 sans taille.
- **Traçabilité ticket → PR → commit** : chaque ticket livré porte ses PR liées.
- **Revue de code avant merge.** **55 des 62 PR de fonctionnalité (89 %)** ont été relues par
  un autre membre avant merge, par revue formelle ou commentaire ; les remontées de `dev` vers
  `main` ne portent que des PR déjà relues.
- **Intégration.** **81 PR mergées** : 62 vers `dev`, 19 vers `main` (6 remontées, 1 réglage
  Sonar, 12 Dependabot). Les cinq membres ont mergé des PR.
- **Décisions écrites.** **20 ADR** versionnées dans `docs/adr/`, dont deux procédures de
  déploiement (0011, 0012) qui relèvent davantage de la note d'exécution que de l'ADR.
- **Points d'avancement** les 15, 17, 18 et 21/09, chacun terminé par une décision ; ceux du 15
  et du 18/09 sont versionnés dans `docs/dailies/`. Le compte rendu du 18/09 a été rédigé après
  coup, le 21/09.
- **Étiquettes par domaine** sur les issues (`feature`, `backend`, `frontend`, `ml`, `infra`,
  `ci/cd`, `test`, `securite`, `pipeline ETL`, `accessibility`).
- **User stories formalisées** (« en tant que... je veux... afin de... ») : non retrouvées
  telles quelles, le besoin fonctionnel est porté par le corps des issues.

---

## 3. Planning, jalons, gestion des risques

### Jalons internes du projet

À ne pas confondre avec la numérotation J1 à J10 du calendrier de formation : ce sont deux
échelles différentes.

| Jalon projet | Échéance (API) | Fermées / total au 24/09 | État |
|---|---|---|---|
| J1 · Environnement et dépôt | 14/09 | 5/5 | clos le 15/09 |
| J2 · Périmètre et choix technologiques | 15/09 | 4/4 | clos le 16/09 |
| J3 · Ingestion et backend | 21/09 | 22/22 | tout fermé, jalon laissé ouvert |
| J4 · Architecture, sécurité, frontend | 22/09 | 24/24 | tout fermé, jalon laissé ouvert |
| J5 · Robustesse et livrables | 23/09 | 5/6 | reste #154 (déclaration IA et RGPD, portée par ce rapport) |
| J6 · Amélioration possible | 28/09 | 7/9 | créé le 21/09 pour le périmètre coupé (§5) ; restent #11 et #54 |

Le point d'avancement du 21/09 donnait le 18/09 et le 21/09 pour J3 et J4 ; l'API donne
aujourd'hui le 21/09 et le 22/09. L'API ne garde pas l'historique des échéances : l'écart est
signalé, pas expliqué.

### Calendrier institutionnel

| Jalon | Contenu | Date |
|---|---|---|
| J1 | Rendu EC01, dossier de conception individuel | fait, 14/09 |
| J9 | Oral EC01, 15 min + ~10 min de questions | jeudi 24/09 |
| J10 | Gel technique 9h00, rendu EC02 à EC06, oral EC02 (15 min + ~5 min de vidéo + ~5 min de questions) | vendredi 25/09 |

### Risques identifiés et leur traitement

| Risque | Impact | Statut au 24/09 |
|---|---|---|
| **`main` en retard sur `dev`** | `main` est la branche par défaut et celle de la production | **Traité.** Six remontées (#125, #152, #160, #161, #163, #165) ; au gel, `main` et `dev` portent le même commit. Sept déploiements de production réussis, le dernier sur le commit gelé |
| Tickets sans assigné (17 au 21/09) | Aucun responsable identifié | **Traité par arbitrage** : coupe du 21/09 (§5), puis assignation. Restent 2 issues ouvertes sans assigné, #55 et #154 |
| Jalon J5 sans assigné (#41, #45, #46, #47) | Preuves attendues pour EC03 et EC04 | **Traité** : les quatre livrés et assignés, DAST (#140), tests d'intégration (#147), e2e Playwright et charge k6 (#148) |
| Aucun scan de code dans le pipeline | Note DevSecOps EC03 / EC04 | **Traité** : SAST Bandit bloquant (#121), DAST OWASP ZAP (#140). **Restent hors CI** : Trivy et gitleaks, joués à la main pour le rapport EC04 |
| Aucun déploiement | Attendu explicite d'EC03 et EC04 | **Traité et constaté** : trois environnements sur la machine du groupe (production sur `main`, recette sur `dev`, dev à la demande), certificats Let's Encrypt, runner auto-hébergé (ADR 0009, 0017, 0018) |
| Montée de version majeure d'Airflow par Dependabot (#135) | Provisionnement et déploiement cassés | **Traité le jour même** (#143) |
| Trois PR immobilisées par un quality gate mal configuré | Blocage de la chaîne de merge | **Traité le 18/09**, en configuration et non par contournement |
| Mémoire de la machine (8 Go) insuffisante pour trois stacks | Arrêts par manque de mémoire | **Traité** : portée à 32 Go sur demande à l'école (ADR 0017) |
| Chiffrement au repos (#42) | Données en clair sur le disque | **Partiel, découvert le 24/09** : la machine est un conteneur LXC où LUKS est impossible ; seules les archives sont chiffrées (SSE-C, ADR 0020), demande adressée à l'école |
| Production sans approbation humaine, branches non protégées | Un push non relu part en production | **Ouvert** : annoncés par l'ADR 0009, laissés à poser par l'ADR 0014, jamais activés ; seule l'administratrice du dépôt peut le faire |
| Services hors dépôt sur la machine : k3s et trois serveurs Vault, installés depuis une branche de travail non fusionnée | Surface exposée que le code livré ne documente pas : l'API k3s et les trois Vault écoutent sur toutes les interfaces, k3s redémarre en boucle depuis le 17/09 | **Découvert le 24/09**, à arbitrer par l'administratrice : le code livré n'en dépend pas (rapport EC04, constat 1) |

---

## 4. Compte rendu d'activité honnête

### Indicateurs, depuis la baseline

**Baseline : 57 issues créées le 14/09**, jour 1. Série quotidienne relevée par l'API :

| Jour | Issues créées | Périmètre | Fermées | Cumul fermées | Ouvertes | PR mergées | Cumul PR |
|---|---|---|---|---|---|---|---|
| 14/09 | 57 | 57 | 5 | 5 | 52 | 3 | 3 |
| 15/09 | 1 | 58 | 10 | 15 | 43 | 7 | 10 |
| 16/09 | 1 | 59 | 8 | 23 | 36 | 10 | 20 |
| 17/09 | 6 | 65 | 10 | 33 | 32 | 9 | 29 |
| 18/09 | 2 | 67 | 6 | 39 | 28 | 9 | 38 |
| 21/09 | 5 | 72 | 16 | 55 | 17 | 11 | 49 |
| 22/09 | 1 | 73 | 2 | 57 | 16 | 18 | 67 |
| 23/09 | 3 | 76 | 11 | 68 | 8 | 12 | 79 |
| 24/09 | 0 | 76 | 4 | 72 | 4 | 2 | 81 |

| Indicateur | 16/09 | 18/09 | 24/09 |
|---|---|---|---|
| Board : Done / In progress / Todo | 19 / 6 / 26 | 33 / 6 / 21 (16h) | **66 / 2 / 1** |
| `Must` faits | 45 % | 66 % | **100 %** (56/56) |
| `Should` et `Could` faits | 0 % | 0 % | 100 % et 67 % |
| Issues fermées / périmètre | 23 / 59 | 39 / 67 | **72 / 76** |

**Deux lectures à défendre.** La priorisation est tenue dans les faits : le premier `Should`
n'a été fermé que le 23/09 à 11h10, quand 54 des 56 `Must` l'étaient déjà. Et le périmètre a dérivé de
57 à 76 issues (+33 %), dont 19 créées en cours de route : la dérive a été absorbée par la coupe
du 21/09 (§5) plutôt que laissée ouverte. Le 22/09 illustre la limite du comptage : 2 issues
fermées, mais 18 PR mergées, le déploiement continu et Terraform, les plus lourdes du projet.

### Livré depuis le 18/09 à 16h00

| PR | Mergée le | Contenu |
|---|---|---|
| #113, #118 | 18 et 21/09 | Détection des alertes internes ; entraînement et scoring LightGBM orchestrés par deux DAGs |
| #114, #124 | 21/09 | Moteur de règles de recommandation (ADR 0006) ; DAG d'alertes et de recommandations (ADR 0008) |
| #112, #138, #146 | 21 et 22/09 | Import depuis l'API Mock borné ; import historique, puis import horaire, orchestrés par Airflow |
| #107, #123 | 21 et 22/09 | Supervision des capteurs par site ; enregistrement du modèle dans le registre MLflow |
| #117, #121 | 21/09 | Reverse proxy Nginx et TLS (ADR 0007) ; SAST Bandit et vue CI/CD |
| #136, #137 | 21/09 | Flux d'alertes du tableau de bord ; vue recommandations |
| #139, #143, #144 | 22/09 | Déploiement continu, runner auto-hébergé (ADR 0009) ; réalignement Airflow 3 ; Terraform provisionne la machine (ADR 0010) |
| #140 | 22/09 | Scan dynamique OWASP ZAP de l'API |
| #147 | 22/09 | Tests d'intégration API, base et ML ; surveillance de dérive (ADR 0013) |
| #148 | 23/09 | CI unifiée (ADR 0014), e2e Playwright et charge k6 (ADR 0015), supervision Prometheus, Alertmanager, Grafana (ADR 0016) |
| #149 | 23/09 | En-tête `Cross-Origin-Resource-Policy` sur toutes les réponses |
| #151 | 23/09 | Troisième environnement, `dev`, déployé à la demande (ADR 0017) |
| #156, #159 | 23/09 | Noms publics, certificats Let's Encrypt par DNS-01, frontal SNI (ADR 0018) |
| #162 | 23/09 | Réconciliation des deux sources de relevés |
| #164 | 24/09 | Garage par environnement, rétention exportée des relevés, chiffrement des archives (ADR 0019, 0020) |
| 6 remontées, #142, 12 Dependabot | 21 au 24/09 | Mises en production, analyse Sonar sautée sur les PR Dependabot, mises à jour de dépendances |

### Ce qui n'a pas été livré, et pourquoi

- **#11 Responsive et #54 comparateur de scénarios** : `Could`, en cours au gel, jalon J6.
  Démonstration sur poste, sans usage mobile dans le scénario du client pilote.
- **#55 Bouton de pic fictif** : ni assigné, ni au board, rien dans le code.
- **#43 Accessibilité** : fermée en doublon le 23/09, au motif qu'elle serait couverte par les
  tests Playwright ; **aucun test d'accessibilité n'existe**. La fermeture est à corriger dans
  l'outil, pas à défendre.
- **#42 Chiffrement au repos** : fermée comme faite, livrée **en partie** (archives seulement),
  pour une raison d'infrastructure découverte le 24/09 (§3).
- **Loki, Trivy et gitleaks en CI, approbation de la production** : prévus ou annoncés, non
  faits.
- **Rotation des rôles** : elle n'a pas eu lieu (§1).

Lecture honnête : tout ticket assigné à quelqu'un a été mené au bout ou reste en cours au gel.
Le retard du 21/09 n'était pas un problème d'exécution individuelle mais de **répartition** : il
a été traité par la coupe et l'assignation, puis rattrapé. Les faiblesses restantes sont de
rigueur de processus, pas de livraison : fermetures d'issues trop généreuses (#42, #43) et
réglages de protection jamais activés.


---

## 5. Périmètre coupé

**Un périmètre coupé et argumenté est un acte de management ; une issue laissée ouverte sans
rien est un trou.** La coupe a été faite le 21/09, jour de l'échéance du J4, et tracée dans
l'outil : un jalon **J6 « Amélioration possible »**, échéance 28/09, donc après le gel. Elle a
servi à ordonner, pas à renoncer : une fois les `Must` faits, une partie du J6 a été livrée
avant le gel.

| Issue | Sujet | Raison de la coupe au 21/09 | Au gel |
|---|---|---|---|
| #11 | Responsive | Démonstration sur poste, aucun usage mobile | en cours, non livré |
| #24 | MinIO, couche bronze | La charge brute est déjà en base (`raw_data`) | **livré autrement** : Garage, jugé plus léger (ADR 0019) |
| #26 | Monitoring Prometheus et Grafana | Classé bonus par le sujet | **livré** (#148, ADR 0016) |
| #36 | Rétention des données | Jeu de démonstration borné | **livré** : export vers Garage puis suppression (#164) |
| #42 | Chiffrement au repos | Données synthétiques, priorité au chiffrement en transit | **partiel** : archives chiffrées, base en clair (ADR 0020) |
| #43 | Accessibilité | Hors des critères de notation technique | fermée en doublon, **non livrée** |
| #54 | Comparateur de scénarios | Confort (`Could`) | en cours, non livré |

Les tests e2e (#46) et de charge (#47), dont la coupe était proposée le 21/09, ont finalement
été livrés (#148). Deux sacrifices restent assumés : **Big Data**, hors de portée dans le temps
imparti, et **RPA avancé**, au-delà de l'orchestration Airflow.

---

## 6. Écarts entre conception (EC01) et réalisation

Le guide d'évaluation le dit : **les écarts entre conception et réalisation font partie du
compte rendu d'activité**. Chaque écart ci-dessous porte sa trace.

| # | Choix du dossier EC01 (14/09) | Réalisé au gel | Verdict |
|---|---|---|---|
| 1 | FastAPI / Python pour l'API | FastAPI, contrat OpenAPI versionné et testé | ✅ Tenu |
| 2 | PostgreSQL 17 + TimescaleDB | Identique, relevés en hypertable (ADR 0001) | ✅ Tenu |
| 3 | JWT + Argon2id, RBAC à 3 rôles | Identique, plus rotation du jeton de rafraîchissement (ADR 0002, 0003) | ✅ Tenu |
| 4 | Une valeur nulle n'est jamais effacée | Qualité de donnée et imputation tracées, gravées par une contrainte `CHECK` | ✅ Tenu |
| 5 | Contrats d'interface figés | Contrat OpenAPI testé, table `prediction` comme frontière ML | ✅ Tenu |
| 6 | Docker Compose plutôt que Kubernetes | Compose, un projet par environnement (ADR 0009, 0017) | ✅ Tenu |
| 7 | On-premise plutôt que cloud public | Machine de l'école, aucune ressource cloud | ✅ Tenu |
| 8 | Traefik en terminaison TLS | Nginx par stack (ADR 0007) et frontal SNI (ADR 0018) | 🔁 Substitué |
| 9 | Prophet + IsolationForest | LightGBM, un modèle global (ADR 0005), alertes internes par règles, dérive surveillée (ADR 0013) | 🔁 Substitué |
| 10 | APScheduler pour l'ETL | Airflow, 7 DAGs : imports, entraînement, scoring, alertes, dérive, rétention | 🔁 Substitué |
| 11 | MinIO, couche bronze | Garage par environnement (ADR 0019) | 🔁 Substitué |
| 12 | Ansible, durcissement et déploiement | Terraform et script rejouable (ADR 0010) ; durcissement non automatisé | ⚠️ Partiel |
| 13 | SOPS + age pour les secrets | Secrets générés sur la machine, hors de Git | ❌ Non fait |
| 14 | Trivy, Bandit, gitleaks en CI | Bandit (#121) et un DAST ZAP non prévu (#140) ; Trivy et gitleaks hors CI | ⚠️ Partiel |
| 15 | Prometheus, Grafana, Loki | Prometheus, Alertmanager, Grafana actifs en production (ADR 0016) ; pas de Loki | ⚠️ Partiel |
| 16 | Runner auto-hébergé, déploiement automatique | `deploy.yml` sur runner auto-hébergé, sept déploiements de production | ✅ Tenu |
| 17 | Deux réseaux Docker, données jamais exposées | Un seul composant exposé, le frontal ; tout le reste sur la boucle locale | 🔁 Intention tenue, autre moyen |

**Décompte sur les 17 choix du dossier : 8 tenus, 5 substitués, 3 partiels, 1 non fait.** Au
23/09, il était de 8 tenus, 4 substitués, 3 partiels et 2 non faits : MinIO est passé de « non
fait » à « substitué » par Garage.

**Hors de cette liste**, le dashboard était prévu en React / Vite ; il est en **Angular 22**
depuis son initialisation le 14/09 (commit `49f4697`, PR #52). Sans effet sur le reste de
l'architecture, puisque le frontend ne connaît que le contrat d'API. Motif : choix de Valentin, développeur
full stack de l'équipe, qui maîtrisait Angular ; aucune objection dans le cadre du projet.

---

## 7. Usage de l'intelligence artificielle

Déclaration exigée par le formateur : outils utilisés, tâches réalisées, valeur ajoutée,
limites constatées, vérifications humaines.

### Déclaration de Johan LEROY

| | |
|---|---|
| **Outil** | Claude Code (Anthropic), en assistant de développement dans le terminal et l'IDE |
| **Tâches** | Aide à la rédaction de code backend, d'infrastructure et de tests, relecture de PR en amont de la revue humaine, rédaction et mise à jour de la documentation d'architecture et des ADR, analyse d'écarts entre le dépôt et les attendus, relevés chiffrés de ce rapport |
| **Valeur ajoutée** | Vitesse sur le travail répétitif (gabarits de tests, migrations, documentation), et surtout **recoupement systématique** : détection d'incohérences entre documentation et code qu'une relecture humaine laisse passer |
| **Limites constatées** | Des **chiffres plausibles mais faux** quand ils ne sont pas recalculés ; des **références à des fichiers inexistants** ; une tendance à **présenter comme acquis** ce qui n'est que prévu (l'approbation de la production, annoncée par deux ADR, n'a jamais été activée) ; des **horodatages en UTC recopiés comme heure locale** |
| **Vérifications humaines** | Tout code généré passe par la CI (lint, typage, tests, couverture, SAST) et par une revue de PR. Tout chiffre publié est réobtenu par une commande (`gh`, `git log`) au moment de la rédaction. Les décisions d'architecture restent prises et signées en ADR par un humain |

### Déclarations des autres membres

Non transmises au moment du gel. Le gabarit reste celui de la déclaration ci-dessus : outil,
tâches, valeur ajoutée, limites, vérifications.

---

## 8. Licences logicielles

**Licence du dépôt** : aucun fichier `LICENSE` au gel. Faute de licence explicite, le code reste
sous le régime par défaut : tous droits réservés à ses auteurs, aucune réutilisation accordée.

**Dépendances, relevées le 24/09** par `pip-licenses` (verrous figés, sans dépendances de dev)
et `license-checker --production` :

| Périmètre | Résultat |
|---|---|
| Backend, ML, Airflow (Python) | MIT, BSD, Apache 2.0 et PSF pour l'essentiel. **Aucune GPL ni AGPL embarquée.** À noter : `psycopg` (ML) sous LGPL 3.0, utilisé comme bibliothèque, sans obligation sur le code appelant ; `certifi` et `pathspec` sous MPL 2.0, copyleft limité au fichier, non modifiés ; `text-unidecode` (Airflow) sous double licence Artistic ou GPL, retenue sous Artistic |
| Frontend, dépendances de production | 12 paquets : 10 MIT, 1 Apache 2.0, 1 0BSD |

**Composants exécutés à côté du produit**, chacun dans son conteneur, sans modification :

| Composant | Rôle | Licence |
|---|---|---|
| Nginx | Reverse proxy, frontal SNI | BSD 2-Clause |
| PostgreSQL · TimescaleDB | Base, séries temporelles | PostgreSQL License · Apache 2.0 pour le cœur, Timescale License pour certaines fonctions de l'image utilisée |
| Apache Airflow, MLflow | Orchestration, registre de modèles | Apache 2.0 |
| Prometheus, Alertmanager, exporteurs, cAdvisor | Supervision | Apache 2.0 |
| **Grafana, Garage, k6** | Tableaux de bord, stockage objet, tirs de charge en CI | **AGPL 3.0** |
| acme.sh | Certificats Let's Encrypt | GPL 3.0 |
| Mailpit | Courriel de développement et d'alerte | MIT |
| Terraform | Infrastructure as code | **BUSL 1.1** : usage interne autorisé, redistribution concurrente interdite |

Les composants AGPL et GPL tournent sans modification, dans des conteneurs séparés : ils
n'imposent rien au code du produit. Point de cohérence : l'ADR 0019 écarte MinIO en citant
notamment sa licence AGPL, que Garage partage ; les autres raisons de l'ADR restent.

---

## 9. Anonymisation et conformité RGPD

- **Les données du projet sont synthétiques.** Les séries de consommation proviennent des CSV
  fournis par l'organisme de formation et de l'API Mock simulée. Aucune donnée de consommation
  réelle d'un client identifiable n'est présente dans le dépôt.
- **Les sites sont désignés par identifiants** (`SITE001` à `SITE007`), sans raison sociale ni
  adresse.
- **Les comptes applicatifs** de test utilisent des adresses de domaine fictif et des mots de
  passe de test. Le compte du scan DAST est un compte `lecteur` jetable.
- **Aucun secret dans le dépôt, vérifié** : scan gitleaks sur tout l'historique le 24/09, 342
  commits hors merges, 8 constats, tous faux positifs après tri ligne à ligne ; aucun `.env`,
  clé, certificat ni state Terraform jamais commité (rapport EC04, preuve 05). C'est le ZIP
  `.git` complet qui est remis au jury : le contrôle porte donc bien sur l'historique.
- **Adresse de la machine** : l'adresse privée de la machine du groupe apparaît dans des
  documents d'exploitation de l'historique git. Adresse non routable, joignable depuis le seul
  réseau de l'école ; elle est masquée dans l'arbre livré.
- **Journal d'audit** : les accès sont tracés en ajout seul (ADR 0004). Cette table contient des
  identifiants d'utilisateurs applicatifs : sur un déploiement réel, elle relèverait d'une durée
  de conservation définie. Elle n'est pas fixée à ce jour : à arrêter avant tout déploiement réel.
- **Dans ce rapport et les supports d'oral** : aucune URL, adresse IP, identifiant de connexion
  ou coordonnée personnelle n'est reproduite. Les identifiants GitHub sont des pseudonymes
  publics, conservés parce qu'ils sont la seule clé de traçabilité vérifiable.

---

## Sources

Relevé du 24/09/2026 à 14h25, commit `9f343e9` :

- **Git** : `git rev-list --count origin/dev` et `--no-merges` · `git log origin/dev
  --no-merges --format=%an | sort | uniq -c` (alias regroupés) · `git log --no-merges
  <merge>^1..<merge>^2` (auteur principal) · `git ls-tree --name-only origin/main docs/adr/` ·
  `git rev-list --count origin/main..origin/dev`
- **API GitHub** : `gh issue list --state all --limit 300 --json
  number,state,assignees,milestone,createdAt,closedAt` · `gh project item-list 2 --owner
  ineszang --format json` · `gh api repos/ineszang/ProjetPiscine_EnerVision/milestones?state=all`
  · `gh pr list --state all --limit 300 --json number,author,mergedBy,mergedAt,baseRefName,reviews`
  · `gh api .../deployments?environment=prod`
- **Licences** : `uv run --frozen --no-dev --with pip-licenses pip-licenses --from=mixed` dans
  chaque projet Python · `npx license-checker@25 --production --summary` dans `apps/frontend`
- `CONSIGNES-PROJET.md`, documents officiels 01, 02 et 05, points d'avancement des 15, 17, 18 et
  21/09, rapport de sécurisation EC04
