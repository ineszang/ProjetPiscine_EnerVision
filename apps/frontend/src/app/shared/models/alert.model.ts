export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AlertType = 'spike' | 'threshold' | 'anomaly' | 'outage' | 'sensor';

export interface Alert {
  alert_id: string;
  timestamp: string;
  site_id: string;
  severity: AlertSeverity;
  type: AlertType;
  message: string;
  value: number;
  threshold: number;
}
