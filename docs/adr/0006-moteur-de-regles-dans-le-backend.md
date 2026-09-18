# 0006 - Le moteur de règles de recommandation vit dans le backend

- Statut : accepté
- Date : 2026-09-18

## Contexte

L'issue #38 demande un « moteur de règles pour recommandations », portée par le label `ml`. Le
schéma tranche déjà la forme du résultat : `recommendation(alert_id, action, explanation,
rule_reference)`, avec `alert_id` en clé étrangère `NOT NULL` et une contrainte d'unicité
`uq_recommendation_alert_rule` sur `(alert_id, rule_reference)`. Une recommandation est donc
**dérivée d'une alerte**, jamais d'une mesure brute ni d'une prévision.

Deux emplacements se disputaient le code :

1. `ml/enervision_ml/`, sur le patron de `enervision_ml.score` livré par #37 : un script autonome
   qui se connecte par `ML_DATABASE_URL`, écrit une table, et que l'API se contente de lire.
   L'[ADR 0005](0005-modele-prediction-lightgbm.md) annonce d'ailleurs #38 de ce côté, en écrivant
   que le scoring, le moteur de recommandations et les tests de dérive « consommeront le même
   module `enervision_ml.features` ».
2. `apps/backend/app/services/`, où `apps/backend/README.md` place les « regles metier ».

## Décision

**Le moteur vit dans `apps/backend/app/services/`**, sous la forme d'un module pur
`recommendation_rules.py` (le catalogue `REGLES`) et d'une méthode `RecommendationService.generate()`
qui l'applique, persiste et valide la transaction.

Trois raisons :

- **Il n'utilise rien du ML.** Le catalogue lit `alert.type`, `alert.severity`, `alert.value` et
  `alert.threshold`. Aucun modèle, aucune feature, aucun `enervision_ml.features` : la phrase de
  l'ADR 0005 vaut pour le scoring (#37) et les tests de dérive (#44/#45), qui manipulent bien des
  features, pas pour des règles sur alertes. Le label `ml` de #38 désigne le lot fonctionnel
  « prédiction et recommandation », pas l'emplacement du code.
- **Il lit et écrit deux tables déjà couvertes par des repositories.** `AlertRepository` sait déjà
  filtrer par site. Le placer dans `ml/` obligerait à réécrire ces accès en SQL brut, et à
  maintenir deux représentations du même domaine.
- **Le déclencheur HTTP n'a de sens que dans l'API.** `POST /recommendations/generate` doit passer
  par `require_role(Role.ADMIN)` et par la session injectée : cela suppose d'être dans
  l'application FastAPI.

Le moteur reste néanmoins **déclenchable hors HTTP**, par `python -m app.cli
generate-recommendations` (cible `make recommendations`), sur le patron de `make ml-score` : rien
n'oblige à exposer un port pour régénérer des recommandations.

## Conséquences

- L'API gagne sa première route d'écriture métier. La checklist de `20-backend.md` s'applique :
  entrée dans `ROLE_MINIMUM` de `tests/api/acces.py`, et `openapi.json` régénéré dans le même
  commit.
- `RecommendationService` n'est plus en lecture seule : il reçoit le `Transaction` Protocol déjà
  utilisé par `AuthService` et `UserService`, et commite lui-même. Les repositories continuent de
  ne pas commiter.
- **L'idempotence est déléguée à la base.** `create_missing()` insère en `ON CONFLICT DO NOTHING`
  sur `uq_recommendation_alert_rule` plutôt que de relire avant d'écrire, ce qui supprime la
  fenêtre entre le contrôle et l'insertion. Corollaire : `rule_reference` est une clé fonctionnelle.
  Une règle dont le sens change prend une référence `-v2` ; renommer une référence livrée
  ferait réapparaître ses recommandations à côté des anciennes.
- **Le moteur ne produira rien tant que `alert` restera vide.** Aucun code ne produit aujourd'hui
  de ligne d'alerte : ni détection interne (#104), ni ingestion de l'API Mock `/alerts`. La chaîne
  s'allume d'elle-même le jour où l'une des deux existe, sans retoucher le moteur.
- Si le projet devait un jour pondérer les recommandations par un score appris, la décision serait
  à rouvrir : le moteur redeviendrait consommateur du pipeline ML.

## Alternatives écartées

- **Module et CLI dans `ml/enervision_ml/`** : cohérent avec le label `ml` et avec la lettre de
  l'ADR 0005, mais impose du SQL brut là où deux repositories existent, et laisse la génération
  hors de portée de l'API. Redeviendrait le bon choix si les règles se mettaient à consommer des
  features ou un modèle.
- **Génération à la volée, sans persistance**, calculée à chaque `GET /recommendations` : supprime
  le besoin d'écriture, mais rend la table `recommendation` et sa contrainte d'unicité inutiles,
  et interdit toute trace de ce qui a été proposé et quand.
- **Table de configuration des règles en base**, plutôt qu'un catalogue en Python : plus souple,
  mais déplace la logique métier hors de la revue de code et hors des tests, pour un besoin que
  rien n'exprime à ce stade.
