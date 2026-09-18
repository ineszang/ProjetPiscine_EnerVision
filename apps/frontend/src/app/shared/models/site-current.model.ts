import { ReadingDataQuality } from './reading.model';

export interface SiteCurrent {
  timestamp: string | null;
  site_id: string;
  site_type: string;
  consumption_kw: number | null;
  consumption_kwh: number | null;
  voltage_v: number | null;
  current_a: number | null;
  power_factor: number | null;
  temperature_celsius: number | null;
  humidity_percent: number | null;
  null_reasons: string[];
  data_quality: ReadingDataQuality;
}
