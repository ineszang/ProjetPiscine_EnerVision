export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AlertType = 'spike' | 'threshold' | 'anomaly' | 'outage' | 'sensor';
export type AlertMetric = 'consumption_kw' | 'consumption_kwh';

export interface Alert {
  alert_id: number;
  site_id: string;
  timestamp: string;
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  value: number | null;
  threshold: number | null;
  metric: AlertMetric | null;
  prediction_id: number | null;
}
