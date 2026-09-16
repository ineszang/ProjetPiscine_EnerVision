import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { StatsService } from './stats.service';
import { environment } from '../../../environments/environment';

describe('StatsService', () => {
  let service: StatsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(StatsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('appelle le bon endpoint et retourne le résumé', () => {
    let result: unknown;
    service.getSummary().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${environment.apiUrl}/stats/summary`);
    expect(req.request.method).toBe('GET');

    req.flush({
      timestamp: '2026-09-15T12:00:00',
      total_sites: 7,
      total_consumption_kw: 1800,
      total_capacity_kw: 3800,
      average_load_percent: 47.4,
      sites: [],
    });

    expect((result as { total_sites: number }).total_sites).toBe(7);
  });
});
