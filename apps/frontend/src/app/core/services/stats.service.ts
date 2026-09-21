import { Service, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { StatsSummary } from '../../shared/models/stats.model';

@Service()
export class StatsService {
  private http = inject(HttpClient);

  getSummary() {
    return this.http.get<StatsSummary>(`${environment.apiUrl}/stats/summary`);
  }
}
