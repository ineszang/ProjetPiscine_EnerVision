import { Service, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { Site } from '../../shared/models/site.model';

@Service()
export class SitesService {
  private http = inject(HttpClient);

  getSites() {
    return this.http.get<Site[]>(`${environment.apiUrl}/sites`);
  }
}
