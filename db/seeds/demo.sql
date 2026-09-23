-- Contrainte : jeu de démonstration pour une base JETABLE (CI, e2e, charge, DAST) - demo.sql.
-- Rejouable : identifiants fixes et `ON CONFLICT DO NOTHING`, ou `NOT EXISTS` là où aucune
-- contrainte d'unicité ne protège la table.
-- Pourquoi : les horodatages suivent `now()`. La fenêtre par défaut de `GET /readings` couvre les
-- 24 dernières heures, et un jeu figé dans le passé laisserait le tableau de bord vide.
-- Piège : `demo-ecole` finit sur une lecture `partial` sans humidité, pour que la supervision des
-- capteurs montre un site dégradé ; au-delà de dix alertes, le fil affiche « Afficher plus ».

BEGIN;

INSERT INTO site (site_id, site_name, site_type, location, capacity_kw, status)
VALUES
    ('demo-siege', 'Siège Part-Dieu', 'office', 'Lyon', 450, 'actif'),
    ('demo-usine', 'Usine de Vénissieux', 'factory', 'Vénissieux', 900, 'actif'),
    ('demo-ecole', 'Groupe scolaire Gratte-Ciel', 'school', 'Villeurbanne', 250, 'maintenance')
ON CONFLICT (site_id) DO NOTHING;

WITH profil (site_id, base_kw, amplitude_kw) AS (
    VALUES ('demo-siege', 180.0, 120.0), ('demo-usine', 520.0, 260.0), ('demo-ecole', 70.0, 60.0)
),
heures AS (
    SELECT date_trunc('hour', now()) - make_interval(hours => n) AS horodatage, n
    FROM generate_series(0, 71) AS n
),
lectures AS (
    SELECT
        p.site_id,
        h.horodatage,
        h.n,
        round((p.base_kw + p.amplitude_kw * greatest(0, sin(pi() * (extract(hour FROM h.horodatage) - 6) / 14)))::numeric, 2)::double precision AS kw,
        extract(isodow FROM h.horodatage) < 6 AND extract(hour FROM h.horodatage) BETWEEN 8 AND 18 AS ouvre
    FROM profil AS p
    CROSS JOIN heures AS h
)
INSERT INTO reading (
    site_id, timestamp, source, consumption_kw, consumption_kwh, consumption_euros,
    voltage_v, current_a, power_factor, temperature_celsius, humidity_percent,
    is_working_hours, data_quality, null_reasons, raw_data
)
SELECT
    site_id,
    horodatage,
    'api_current',
    kw,
    kw,
    round((kw * 0.19)::numeric, 2),
    230.0,
    round((kw * 1000 / (230.0 * 3 * 0.95))::numeric, 1)::double precision,
    0.95,
    19.5 + 3 * sin(pi() * extract(hour FROM horodatage) / 12),
    CASE WHEN site_id = 'demo-ecole' AND n = 0 THEN NULL ELSE 45.0 END,
    ouvre,
    CASE WHEN site_id = 'demo-ecole' AND n = 0 THEN 'partial' ELSE 'good' END,
    CASE WHEN site_id = 'demo-ecole' AND n = 0 THEN ARRAY['humidity_sensor_failure'] END,
    '{}'::jsonb
FROM lectures
ON CONFLICT DO NOTHING;

INSERT INTO prediction (site_id, target_at, target_metric, period_minutes, predicted_value, model_reference, status)
SELECT s.site_id, date_trunc('hour', now()) + interval '1 hour', 'consumption_kwh', 60, s.valeur, 'demo-seed', 'available'
FROM (VALUES ('demo-siege', 214.0), ('demo-usine', 610.5), ('demo-ecole', 88.2)) AS s (site_id, valeur)
WHERE NOT EXISTS (
    SELECT 1 FROM prediction AS p
    WHERE p.site_id = s.site_id
      AND p.model_reference = 'demo-seed'
      AND p.target_at = date_trunc('hour', now()) + interval '1 hour'
);

INSERT INTO alert (source_alert_id, site_id, source, timestamp, type, severity, message, value, threshold, metric, raw_data)
SELECT a.id, a.site_id, 'enervision', now() - make_interval(hours => a.age_h), a.type, a.severite, a.message, a.valeur, a.seuil, a.metrique, '{}'::jsonb
FROM (
    VALUES
        ('demo-01', 'demo-siege', 1, 'spike', 'high', 'Pic de consommation à 312 kW', 312.0, 250.0, 'consumption_kw'),
        ('demo-02', 'demo-siege', 3, 'threshold', 'medium', 'Seuil de 80 % de la capacité franchi', 372.0, 360.0, 'consumption_kw'),
        ('demo-03', 'demo-siege', 6, 'anomaly', 'low', 'Consommation nocturne inhabituelle', 205.0, NULL, 'consumption_kw'),
        ('demo-04', 'demo-siege', 9, 'sensor', 'medium', 'Capteur de température muet', NULL, NULL, 'temperature_celsius'),
        ('demo-05', 'demo-siege', 20, 'outage', 'critical', 'Coupure de courant de 2 heures', 0.0, NULL, 'consumption_kw'),
        ('demo-06', 'demo-usine', 2, 'spike', 'critical', 'Pic de consommation à 1 020 kW', 1020.0, 850.0, 'consumption_kw'),
        ('demo-07', 'demo-usine', 4, 'threshold', 'high', 'Seuil de 90 % de la capacité franchi', 830.0, 810.0, 'consumption_kw'),
        ('demo-08', 'demo-usine', 8, 'anomaly', 'medium', 'Facteur de puissance dégradé', 0.71, 0.85, 'power_factor'),
        ('demo-09', 'demo-usine', 14, 'outage', 'high', 'Perte de mesure sur la ligne principale', NULL, NULL, 'consumption_kw'),
        ('demo-10', 'demo-usine', 30, 'sensor', 'low', 'Capteur électrique intermittent', NULL, NULL, 'voltage_v'),
        ('demo-11', 'demo-ecole', 1, 'sensor', 'high', 'Capteur d''humidité muet', NULL, NULL, 'humidity_percent'),
        ('demo-12', 'demo-ecole', 5, 'anomaly', 'low', 'Chauffage actif hors des heures d''ouverture', 96.0, NULL, 'consumption_kw'),
        ('demo-13', 'demo-ecole', 12, 'threshold', 'medium', 'Seuil de 60 % de la capacité franchi', 158.0, 150.0, 'consumption_kw'),
        ('demo-14', 'demo-ecole', 40, 'spike', 'medium', 'Pic de consommation à 190 kW', 190.0, 160.0, 'consumption_kw')
) AS a (id, site_id, age_h, type, severite, message, valeur, seuil, metrique)
ON CONFLICT DO NOTHING;

INSERT INTO drift_report (window_start, window_end, n_observations, mae, mape, bias, reference_mae, coverage_ratio, insufficient_data_ratio, model_references, status, reason, site_id)
SELECT date_trunc('day', now()) - interval '7 days', date_trunc('day', now()), d.n, d.mae, d.mape, d.biais, 11.0, 0.98, 0.0, ARRAY['demo-seed'], d.statut, d.raison, d.site_id
FROM (
    VALUES
        ('demo-siege', 168, 9.4, 0.052, -1.2, 'stable', NULL),
        ('demo-usine', 168, 31.8, 0.061, 14.5, 'derive', 'MAE supérieure à 1,5 fois la référence'),
        ('demo-ecole', 120, 6.1, 0.083, 0.4, 'stable', NULL),
        (NULL, 456, 16.9, 0.064, 5.1, 'stable', NULL)
) AS d (site_id, n, mae, mape, biais, statut, raison)
ON CONFLICT DO NOTHING;

COMMIT;
