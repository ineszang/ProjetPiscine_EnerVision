import { PredictionSummary } from '../../shared/models/prediction.model';

export const PREDICTIONS_FIXTURE: PredictionSummary = {
  timestamp: '2026-09-18T09:00:00Z',
  sites: [
    {
      site_id: 'SITE001',
      site_name: 'Bureau Paris La Défense',
      prediction: {
        target_at: '2026-09-18T10:00:00Z',
        target_metric: 'consumption_kwh',
        period_minutes: 60,
        predicted_value: 89.2,
        status: 'available',
        failure_reason: null,
        model_reference: 'lightgbm-16b431449a50',
        created_at: '2026-09-18T09:00:00Z',
      },
    },
    {
      site_id: 'SITE002',
      site_name: 'Usine Lyon Vénissieux',
      prediction: {
        target_at: '2026-09-18T10:00:00Z',
        target_metric: 'consumption_kwh',
        period_minutes: 60,
        predicted_value: 561.4,
        status: 'available',
        failure_reason: null,
        model_reference: 'lightgbm-16b431449a50',
        created_at: '2026-09-18T09:00:00Z',
      },
    },
    {
      site_id: 'SITE003',
      site_name: 'Data Center Marseille',
      prediction: {
        target_at: '2026-09-18T10:00:00Z',
        target_metric: 'consumption_kwh',
        period_minutes: 60,
        predicted_value: null,
        status: 'insufficient_data',
        failure_reason:
          "Historique insuffisant : moins de 168h de consumption_kwh disponibles pour ce site.",
        model_reference: 'lightgbm-16b431449a50',
        created_at: '2026-09-18T09:00:00Z',
      },
    },
    {
      site_id: 'SITE004',
      site_name: 'Bureau Bordeaux',
      prediction: {
        target_at: '2026-09-18T10:00:00Z',
        target_metric: 'consumption_kwh',
        period_minutes: 60,
        predicted_value: 58.9,
        status: 'available',
        failure_reason: null,
        model_reference: 'lightgbm-16b431449a50',
        created_at: '2026-09-18T09:00:00Z',
      },
    },
    {
      site_id: 'SITE005',
      site_name: 'Usine Toulouse',
      prediction: {
        target_at: '2026-09-18T10:00:00Z',
        target_metric: 'consumption_kwh',
        period_minutes: 60,
        predicted_value: 402.7,
        status: 'available',
        failure_reason: null,
        model_reference: 'lightgbm-16b431449a50',
        created_at: '2026-09-18T09:00:00Z',
      },
    },
    {
      site_id: 'SITE006',
      site_name: 'Bureau Lille',
      prediction: {
        target_at: '2026-09-18T10:00:00Z',
        target_metric: 'consumption_kwh',
        period_minutes: 60,
        predicted_value: 91.3,
        status: 'available',
        failure_reason: null,
        model_reference: 'lightgbm-16b431449a50',
        created_at: '2026-09-18T09:00:00Z',
      },
    },
    {
      // Illustre le cas d'un site jamais scoré : `prediction` reste `null`, pas un statut inventé
      // (même contrat que `PredictionService.summary()` côté backend).
      site_id: 'SITE007',
      site_name: 'Data Center Nantes',
      prediction: null,
    },
  ],
};
