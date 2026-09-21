export type PredictionStatus = 'available' | 'insufficient_data' | 'error';
export type PredictionTargetMetric = 'consumption_kwh' | 'consumption_kw';

export interface SitePrediction {
  target_at: string;
  target_metric: PredictionTargetMetric;
  period_minutes: number | null;
  predicted_value: number | null;
  status: PredictionStatus;
  failure_reason: string | null;
  model_reference: string;
  created_at: string;
}

export interface SitePredictionSummary {
  site_id: string;
  site_name: string;
  prediction: SitePrediction | null;
}

export interface PredictionSummary {
  timestamp: string;
  sites: SitePredictionSummary[];
}
