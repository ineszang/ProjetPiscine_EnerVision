import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  const tokenResponse = {
    access_token: 'abc123',
    token_type: 'bearer',
    expires_in: 900,
    principal: {
      id: '1',
      email: 'a@a.com',
      role: 'admin' as const,
      kind: 'human' as const,
      must_change_password: false,
    },
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('stocke le token et le principal après un login réussi', () => {
    service.login({ email: 'a@a.com', password: 'secret' }).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/auth/login`);
    expect(req.request.withCredentials).toBe(true);
    req.flush(tokenResponse);

    expect(service.getAccessToken()).toBe('abc123');
    expect(service.principal()?.email).toBe('a@a.com');
    expect(service.isAuthenticated()).toBe(true);
  });

  it('efface la session au logout', () => {
    service.login({ email: 'a@a.com', password: 'secret' }).subscribe();
    httpMock.expectOne(`${environment.apiUrl}/auth/login`).flush(tokenResponse);

    service.logout().subscribe();
    httpMock.expectOne(`${environment.apiUrl}/auth/logout`).flush(null);

    expect(service.getAccessToken()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });

  it("ne déclenche qu'un seul appel réseau si refreshShared est appelé plusieurs fois avant la réponse", () => {
    service.refreshShared().subscribe();
    service.refreshShared().subscribe();
    service.refreshShared().subscribe();

    const requests = httpMock.match(`${environment.apiUrl}/auth/refresh`);
    expect(requests.length).toBe(1);
    requests[0].flush(tokenResponse);
  });

  it('met à jour la session après un changement de mot de passe réussi', () => {
    service.changePassword({ current_password: 'old', new_password: 'new-password-1234' }).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/auth/password`);
    req.flush(tokenResponse);

    expect(service.getAccessToken()).toBe('abc123');
  });

  it('récupère le principal courant via /auth/me', () => {
  let result: unknown;
  service.me().subscribe((r) => (result = r));

  const req = httpMock.expectOne(`${environment.apiUrl}/auth/me`);
  expect(req.request.method).toBe('GET');
  req.flush(tokenResponse.principal);

  expect(result).toEqual(tokenResponse.principal);
});
});
