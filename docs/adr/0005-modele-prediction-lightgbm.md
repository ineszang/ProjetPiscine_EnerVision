# 0005 - Modèle de prédiction de consommation : LightGBM

- Statut : accepté
- Date : 2026-09-17

## Contexte

Le schéma `prediction` contraint déjà la forme de la solution (deux cibles de régression,
`consumption_kw` instantané et `consumption_kwh` sur `period_minutes`, un statut
`insufficient_data` à détecter explicitement), mais aucun modèle n'était choisi. Trois
contraintes non négociables cadrent le choix, discutées dans l'issue #89 :

1. **EC06** (grille de notation individuelle) exige un modèle **entraîné, versionné avec
   MLflow**, exposé via un endpoint fonctionnel, avec **surveillance du drift** en production.
2. **Aucun GPU dédié** : l'infra tourne on-premise sur une VM à 4 CPU / 8 Gio RAM (ou
   `Standard_B2s`/`B2ms` côté Azure, 2 vCPU max) — Azure Machine Learning est de toute façon
   bloqué par la politique Azure du projet.
3. **Délai serré** : le jalon J3 arrive à échéance le lendemain de la décision, J4 concentre déjà
   26 issues sur 4 jours. Un modèle long à mettre en œuvre retarde la chaîne complète (service de
   scoring #37, moteur de recommandations #38, tests ML #44/#45, tous bloqués par ce choix).

Le jeu de données est déjà disponible (`all_sites_combined.csv`, fourni par le formateur) : 7
sites, 2 ans au pas horaire (~17 500 lignes/site), avec `temperature_celsius`,
`humidity_percent`, `solar_irradiance_wm2` en régresseurs exogènes et des features calendaires
déjà dérivées.

## Options comparées

| Critère | Prophet | LightGBM/XGBoost | NeuralProphet | SARIMA | Holt-Winters | Mistral (LLM) |
|---|---|---|---|---|---|---|
| Saisonnalités multiples (jour/semaine/an) | Oui, nativement | Oui, via features engineered | Oui, nativement, + autorégression | Une seule, lourd à régler (SARIMAX) | Une seule, aucune | Non conçu pour ça |
| Régresseurs exogènes | Oui, mais doivent être connus dans le futur au moment de la prédiction | Oui, via lags/moyennes glissantes sur le passé | Oui, natif | Difficile en multivarié | Aucun support | Contexte de prompt seulement, non appris |
| Coût de calcul (VM sans GPU) | Faible | Faible | Élevé (deep learning) | Faible | Faible | Élevé à prohibitif |
| Versionnable MLflow | Oui, nativement | Oui, nativement | Pas de support direct | Oui, générique | Pas de support direct | Rien à versionner (pas un modèle entraîné) |
| Granularité | Un modèle par site (ou par site × métrique) | Un seul modèle global sur tous les sites | Un par site | Un par site | Un par site | — |
| Effort avant l'échéance | Faible | Moyen (feature engineering) | Élevé | Moyen à élevé | Faible en soi | Élevé, ou factice |

## Décision

**LightGBM, un seul modèle global** couvrant tous les sites, plutôt qu'un modèle par site
(Prophet) ou par famille de site. Cible : `consumption_kwh`, avec `period_minutes` comme feature
d'entrée plutôt que comme étape d'agrégation post-prédiction. Suivi et versioning via **MLflow**
(tracking + registre de modèles), sur le magasin local par défaut dans un premier temps —
l'hébergement sur l'infra k3s reste une question ouverte, non bloquante pour démarrer.

Raisons retenues, au-delà du tableau ci-dessus :

- **Un modèle global plutôt qu'un modèle par site** évite la fragilité des sites les moins
  fournis en historique : ils bénéficient de ce qu'apprennent les autres sites, ce qu'un Prophet
  par site ne permet pas.
- **Aucune dépendance à une prévision météo future.** Prophet exige que ses régresseurs
  (`add_regressor`) soient connus au moment prédit ; `temperature_celsius`,
  `humidity_percent` et `solar_irradiance_wm2` sont des mesures passées, pas des prévisions, et
  aucune source de prévision météo n'existe dans le projet. LightGBM s'en sort avec des features
  de lag/moyenne glissante calculées sur l'historique déjà présent dans `reading`, cf.
  `ml/enervision_ml/features.py` — un choix qui vaut aussi bien à l'entraînement qu'au futur
  scoring.
- **Apprentissage direct sur `consumption_kwh`** avec `period_minutes` en feature, sans étape
  d'agrégation intermédiaire que la sortie continue de Prophet aurait demandée.
- **Coût de calcul compatible avec l'infra on-premise sans GPU.**

Débat complet, comparatif détaillé et décision finale : issue #89 (Johan, phyri0s,
ValentinDeFaria), actée en réunion d'équipe du 2026-09-17 et validée par l'ensemble de l'équipe.

## Conséquences

- Le pipeline d'entraînement (`ml/`, ce commit) lit `reading` + `site` par connexion PostgreSQL
  directe et construit ses features par lags/moyennes glissantes plutôt que par régresseurs
  contemporains, cf. `docs/ML-START.md`.
- Le rôle PostgreSQL dédié `enervision_ml` (lecture seule sur `reading`/`site`) n'est pas encore
  provisionné : dette déjà assumée par l'ADR 0003 pour les comptes ETL/ML, `ML_DATABASE_URL`
  pointe pour l'instant vers la même base que le backend applicatif en développement.
- Le service de scoring (#37), le moteur de recommandations (#38) et les tests de dérive
  (#44/#45) restent à construire ; ils consommeront le même module `enervision_ml.features`, qui
  doit rester strictement identique entre entraînement et scoring pour éviter un train/serve skew
  silencieux.
- La surveillance de drift exigée par EC06 n'est pas encore implémentée : ce ticket ne livre que
  l'entraînement et son suivi MLflow (paramètres, métriques, artefact modèle), pas le monitoring
  en production.
- L'hébergement de MLflow sur l'infra k3s reste une question ouverte ; le magasin SQLite local
  (`ml/mlflow.db`, ignoré par git) suffit pour l'instant à comparer des runs sur un poste.

## Alternatives écartées

- **Prophet** : proposition initiale, écartée après débat pour les raisons ci-dessus (modèle par
  site, dépendance à une météo future indisponible, agrégation kWh en post-traitement). Reste un
  candidat solide si un jour le projet doit produire une décomposition tendance/saisonnalité
  explicable pour un usage différent.
- **Mistral (LLM)** : aucun produit dédié aux séries temporelles ; interroger un LLM généraliste
  ne constitue pas un modèle entraîné et versionnable au sens MLflow, et le fine-tuning est hors
  budget de calcul et hors délai.
- **SARIMA** : ne gère pas nativement plusieurs régresseurs exogènes ; réglage (p,d,q,P,D,Q) plus
  long que le délai disponible.
- **NeuralProphet** : fait tout ce que fait Prophet et apprend en plus des motifs autorégressifs,
  mais coûte plus cher en calcul (pas de GPU disponible) et n'a pas d'outil MLflow direct — piste
  d'évolution possible, non engageante à ce stade.
- **Holt-Winters** : écarté d'entrée, pas seulement différé — aucun support de régresseurs
  exogènes, alors que la météo et l'irradiance sont nécessaires ici.
- **CatBoost** : même famille que LightGBM, gère nativement les colonnes catégorielles (comme
  `site_type`) sans encodage manuel. Non rejeté, différé : candidat à comparer si LightGBM
  plafonne en précision.
