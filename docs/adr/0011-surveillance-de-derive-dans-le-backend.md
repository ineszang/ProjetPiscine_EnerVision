# 0011 - La surveillance de dérive vit dans le backend et écrit sa propre table

- Statut : accepté
- Date : 2026-09-22

## Contexte

L'issue #45 demande des tests d'intégration API ↔ DB ↔ ML. Trois documents du dépôt annoncent
par ailleurs, depuis le jalon J3, une surveillance de dérive qui n'existe nulle part :
`docs/architecture/00-vue-ensemble.md` (« Surveillance de dérive (EC06, #44/#45) pas encore
construite »), `docs/ML-START.md` (« la dette qui subsiste est la surveillance de dérive »), et
le docstring de `write_predictions()` dans `ml/enervision_ml/score.py`, qui justifie l'absence
d'unicité sur `(site_id, target_at)` par la comparaison future entre prévu et réalisé.

La matière première est en base : `prediction` porte ce que le modèle a annoncé, `reading` ce
qui est réellement arrivé. Restaient trois questions : où vit le calcul, à quoi on compare, et
où atterrit le résultat.

## Décision

**Le calcul vit dans `apps/backend`** : `repositories/drift.py` pour le SQL, `services/drift.py`
pour la logique, `monitoring/drift.py` pour la CLI, `api/v1/endpoints/monitoring.py` pour la
lecture. Le dossier `ml/` ne gagne pas une ligne.

**Le résultat est persisté** dans une table `drift_report`, une ligne par site plus une ligne
globale que `site_id` à NULL désigne.

**La comparaison oppose deux fenêtres vives de 168 h**, la récente et celle qui la précède, et
le verdict a trois valeurs : `stable`, `derive`, `indetermine`.

### Pourquoi le backend, alors que le sujet est le modèle

- **`prediction` n'est pas dans le périmètre de `ML_DATABASE_URL`.** `enervision_ml/config.py`,
  `docs/ML-START.md` et l'[ADR 0003](0003-autorisation-rbac-a-trois-roles.md) désignent pour
  cette variable un rôle PostgreSQL restreint **en lecture sur `reading` et `site`**. Mettre la
  dérive dans `ml/` obligerait à élargir ce rôle à `prediction`, et à l'écriture : ce serait
  contredire par le code la dette de moindre privilège que ces trois documents ont posée par
  écrit.
- **L'alignement prévu contre réalisé existe déjà ici, une fois.** `AlertService._detect_anomaly`
  croise `reading` et `prediction` sur le même instant, et `PredictionRepository.list_since`
  porte déjà le piège des runs empilés. Le réécrire en SQL brut dans `ml/` créerait une seconde
  source de vérité sur « quelle prédiction correspond à quelle lecture », ce que
  l'[ADR 0006](0006-moteur-de-regles-dans-le-backend.md) a déjà refusé pour les règles.
- **La frontière de `docs/ML-START.md` tient.** FastAPI ne fait toujours pas tourner LightGBM :
  la dérive lit deux tables et compare des nombres, elle n'évalue aucun modèle.

**Conséquence assumée** : `enervision_ml.metrics.regression_metrics` n'est pas réutilisable, le
backend n'important pas `enervision_ml`. MAE, MAPE et biais sont donc réécrits, une quinzaine de
lignes. Cette duplication n'est pas celle que `build_features` interdit : une divergence de
features est silencieuse et ruine les prévisions sans erreur, une divergence sur une moyenne
d'écarts absolus est attrapée par le premier test à valeurs connues.

### Ce qu'on mesure, et les deux dédoublonnages obligatoires

La paire est `prediction ⋈ reading` sur `(site_id, target_at = timestamp)`, restreinte aux
prédictions `available`. Elle exige un `DISTINCT ON` **des deux côtés** :

- `prediction` n'a pas d'unicité sur `(site_id, target_at)`, chaque run de scoring empile une
  ligne. On retient la plus récente, celle que sert `GET /api/v1/predictions`, départagée par
  `prediction_id` : `created_at` vaut l'heure de début de transaction et ne distingue pas deux
  lignes du même run.
- `uq_reading_source` autorise deux lectures au même instant quand la `source` diffère. Sans
  dédoublonnage, la jointure compterait cette heure deux fois et pondérerait doublement le site.

La fenêtre est **fermée à droite par un délai de grâce de 2 h** : le réalisé de la dernière
heure n'est pas encore ingéré, et l'inclure ferait chuter le taux de couverture à chaque
exécution, pour une raison qui n'a rien à voir avec le modèle.

Métriques retenues : `mae` (la métrique même qu'optimise LightGBM), **`bias` signé** (une MAE qui
monte dit « moins bon », un biais qui s'éloigne de zéro dit « le modèle se trompe toujours du
même côté », signature d'un décalage de distribution), `mape`, `n_observations`,
`coverage_ratio` et `insufficient_data_ratio` (qui mesurent le pipeline, pas le modèle), et la
liste des `model_references` vus dans la fenêtre : une MAE qui saute à l'instant exact où le
modèle change n'est pas une dérive, c'est une régression de réentraînement.

## Alternatives écartées

| Écartée | Raison |
|---|---|
| Comparer à la métrique MLflow de l'entraînement | Ce ne sont pas les mêmes grandeurs : `train.py` mesure un backtest où la météo de l'heure cible est connue, le scoring prévoit une heure future dont la météo est `NaN` et dont `is_working_hours` est recopié. Le verdict serait « dérive » dès le premier jour. Et le backend devrait importer `mlflow`, ce que la frontière de ML-START interdit. |
| Écrire le résultat dans `alert` | `ck_alert_source` et `ck_alert_type` bornent les valeurs autorisées, `alert.site_id` est `NOT NULL` et n'accueillerait donc pas la ligne globale, et toute alerte est ensuite relue par le moteur de recommandations, qui devrait apprendre une règle qui ne le concerne pas (ADR 0006). |
| Une jauge Prometheus | `monitoring/` ne contient que des `.gitkeep` et aucun collecteur ne lit `/metrics` : une jauge que personne ne scrute n'est pas une preuve. Le calcul est de surcroît un traitement par lot, pas le processus qui sert l'API : la jauge disparaîtrait avec lui. |
| Ne rien persister, journaliser seulement | La question posée à un jury est « comment savez-vous que le modèle se dégrade ? ». La réponse est une série dans le temps, pas une ligne de journal perdue avec le conteneur. Sans ligne écrite, l'endpoint n'a rien à lire et le test d'intégration rien à vérifier. |
| Une tâche de plus dans le DAG `alertes` | La fenêtre fait 168 h : la recalculer chaque heure écrirait vingt-quatre lignes identiques par jour. Surtout, un échec de dérive ferait rougir `alertes` et laisserait croire que la détection a échoué. |

## Conséquences

- Une migration ajoute `drift_report`. Son idempotence passe par un **index unique à
  `coalesce(site_id, '')`** et non par une `UniqueConstraint` : deux lignes globales ont toutes
  deux `site_id` à NULL, et NULL n'est égal à rien, pas même à lui-même. Même forme que
  `uq_reading_source`.
- `GET /api/v1/monitoring/drift` est réservé à partir du rôle `operateur` : c'est l'opérateur
  qui agit sur un pipeline dégradé, pas l'administrateur de comptes. La route est classée dans
  `tests/api/acces.py`, donc couverte gratuitement par la matrice de rôles rejouée avec de vrais
  jetons.
- Un DAG `derive` quotidien l'ordonnance, sans reprise : rejouer une dérive la redéclarerait à
  l'identique.
- La CLI sort en code non nul sous `--fail-on-drift` seulement. Par défaut, constater une dérive
  n'est pas un échec d'exécution.

## Limite connue

`enervision_ml.score --now` ne rejoue pas l'historique : `load_recent_from_database` n'a pas de
borne haute, et `build_scoring_frame` part toujours de la dernière lecture connue. Aucune boucle
de rattrapage ne peut donc fabriquer de paires prévu/réalisé sur des données figées, et la
dérive répond `indetermine` tant que le scoring n'a pas tourné plusieurs fois en exploitation.
