export type SensorStatus = 'ok' | 'failing';
export type OverallStatus = 'ok' | 'degraded' | 'critical';

export interface SensorDiagnostic {
  status: SensorStatus;
  since: string | null;
}

export interface SiteSensors {
  consumption: SensorDiagnostic;
  electrical: SensorDiagnostic;
  temperature: SensorDiagnostic;
  humidity: SensorDiagnostic;
  network: SensorDiagnostic;
  [key: string]: SensorDiagnostic;
}

export interface SiteSensorStatus {
  site_id: string;
  site_name: string;
  sensors: SiteSensors;
  overall: OverallStatus;
}

export interface SensorStatusResponse {
  timestamp: string;
  sites: SiteSensorStatus[];
}
