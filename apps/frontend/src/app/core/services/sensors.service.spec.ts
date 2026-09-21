import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { SensorsService } from './sensors.service';
import { environment } from '../../../environments/environment';

describe('SensorsService', () => {
  let service: SensorsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SensorsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it("appelle l'endpoint /sensors/status et retourne la réponse", () => {
    let result: unknown;
    service.getStatus().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${environment.apiUrl}/sensors/status`);
    expect(req.request.method).toBe('GET');

    req.flush({
      timestamp: '2026-09-18T08:00:00',
      sites: [
        {
          site_id: 'SITE001',
          site_name: 'Test',
          overall: 'ok',
          sensors: {
            consumption: { status: 'ok', since: null },
            electrical: { status: 'ok', since: null },
            temperature: { status: 'ok', since: null },
            humidity: { status: 'ok', since: null },
            network: { status: 'ok', since: null },
          },
        },
      ],
    });

    expect((result as { sites: unknown[] }).sites.length).toBe(1);
  });
});
