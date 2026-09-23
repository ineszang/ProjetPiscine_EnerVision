import { Service, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { Alert, AlertSeverity } from '../../shared/models/alert.model';

export interface AlertFilters {
  site_id?: string;
  severity?: AlertSeverity;
}

@Service()
export class AlertsService {
  private http = inject(HttpClient);

  getAlerts(filters: AlertFilters = {}) {
    let params = new HttpParams();
    if (filters.site_id) {
      params = params.set('site_id', filters.site_id);
    }
    if (filters.severity) {
      params = params.set('severity', filters.severity);
    }
    return this.http.get<Alert[]>(`${environment.apiUrl}/alerts`, { params });
  }
}
