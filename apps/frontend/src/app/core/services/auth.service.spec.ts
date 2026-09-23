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

  it('garde le mot de passe provisoire pour un seul changement quand il doit être changé', () => {
    service.login({ email: 'a@a.com', password: 'Provisoire' }).subscribe();
    httpMock.expectOne(`${environment.apiUrl}/auth/login`).flush({
      ...tokenResponse,
      principal: { ...tokenResponse.principal, must_change_password: true },
    });

    expect(service.takeProvisionalPassword()).toBe('Provisoire');
    expect(service.takeProvisionalPassword()).toBeNull();
  });

  it('ne garde aucun mot de passe quand il est déjà définitif, ni après la fin de session', () => {
    service.login({ email: 'a@a.com', password: 'Definitif' }).subscribe();
    httpMock.expectOne(`${environment.apiUrl}/auth/login`).flush(tokenResponse);
    expect(service.takeProvisionalPassword()).toBeNull();

    service.login({ email: 'a@a.com', password: 'Provisoire' }).subscribe();
    httpMock.expectOne(`${environment.apiUrl}/auth/login`).flush({
      ...tokenResponse,
      principal: { ...tokenResponse.principal, must_change_password: true },
    });
    service.clearSession();
    expect(service.takeProvisionalPassword()).toBeNull();
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

  it('vérifie la validité du jeton de reset via GET /auth/reset-password/validate', () => {
    let result: { valid: boolean } | undefined;
    service.validateResetToken('un-secret-opaque').subscribe((r) => (result = r));

    const req = httpMock.expectOne(
      `${environment.apiUrl}/auth/reset-password/validate?token=un-secret-opaque`
    );
    expect(req.request.method).toBe('GET');
    req.flush({ valid: true });

    expect(result).toEqual({ valid: true });
  });
});
