import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ReadingsService } from './readings.service';
import { environment } from '../../../environments/environment';

describe('ReadingsService', () => {
  let service: ReadingsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ReadingsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it("demande l'historique du site avec la fenêtre temporelle donnée", () => {
    let result: unknown;
    service
      .getHistory('SITE001', '2026-09-16T00:00:00Z', '2026-09-17T00:00:00Z')
      .subscribe((r) => (result = r));

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/readings` && r.method === 'GET',
    );
    expect(req.request.params.get('site_id')).toBe('SITE001');
    expect(req.request.params.get('start')).toBe('2026-09-16T00:00:00Z');
    expect(req.request.params.get('end')).toBe('2026-09-17T00:00:00Z');

    req.flush([{ reading_id: 1, site_id: 'SITE001', consumption_kw: 12.5 }]);

    expect((result as unknown[]).length).toBe(1);
  });

  it('ne pose pas de paramètres start/end quand ils sont omis', () => {
    service.getHistory('SITE001').subscribe();

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/readings` && r.method === 'GET',
    );
    expect(req.request.params.has('start')).toBe(false);
    expect(req.request.params.has('end')).toBe(false);

    req.flush([]);
  });
});
