import { Service, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { Alert } from '../../shared/models/alert.model';

@Service()
export class AlertsService {
  private http = inject(HttpClient);

  getAlerts() {
    return this.http.get<Alert[]>(`${environment.apiUrl}/alerts`);
  }
}
