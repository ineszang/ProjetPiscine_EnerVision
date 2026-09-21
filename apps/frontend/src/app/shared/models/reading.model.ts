export type ReadingSource = 'csv' | 'api_current' | 'api_history';
export type ReadingDataQuality = 'good' | 'partial' | 'degraded' | 'critical';

export interface Reading {
  reading_id: number;
  site_id: string;
  timestamp: string;
  source: ReadingSource;
  consumption_kw: number | null;
  consumption_kwh: number | null;
  consumption_euros: string | null;
  voltage_v: number | null;
  current_a: number | null;
  power_factor: number | null;
  temperature_celsius: number | null;
  humidity_percent: number | null;
  solar_irradiance_wm2: number | null;
  is_working_hours: boolean | null;
  data_quality: ReadingDataQuality | null;
  null_reasons: string[] | null;
  imputed_values: Record<string, unknown> | null;
  imputation_method: string | null;
}
