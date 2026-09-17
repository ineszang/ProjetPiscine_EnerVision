import { Service, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { Reading } from '../../shared/models/reading.model';

@Service()
export class ReadingsService {
  private http = inject(HttpClient);

  getLatest(siteId: string) {
    return this.http.get<Reading | null>(`${environment.apiUrl}/sites/${siteId}/current`);
  }

  getHistory(siteId: string, start?: string, end?: string) {
    let params = new HttpParams().set('site_id', siteId);
    if (start) {
      params = params.set('start', start);
    }
    if (end) {
      params = params.set('end', end);
    }
    return this.http.get<Reading[]>(`${environment.apiUrl}/readings`, { params });
  }
}
