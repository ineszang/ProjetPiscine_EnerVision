export interface SiteSummary {
  site_id: string;
  site_name: string;
  current_consumption_kw: number | null;
  capacity_kw: number;
  load_percent: number | null;
  data_quality: 'good' | 'partial' | 'degraded' | 'critical';
}

export interface StatsSummary {
  timestamp: string;
  total_sites: number;
  total_consumption_kw: number;
  total_capacity_kw: number;
  average_load_percent: number;
  sites: SiteSummary[];
}
