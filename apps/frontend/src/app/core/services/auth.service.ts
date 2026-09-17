import { Service, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, finalize, shareReplay } from 'rxjs';
import { LoginRequest, PasswordChangeRequest, Principal, TokenResponse } from '../../shared/models/auth.model';
import { environment } from '../../../environments/environment';

@Service()
export class AuthService {
  private http = inject(HttpClient);

  // Jamais de localStorage/sessionStorage/cookie côté JS : juste un signal en
  // mémoire. Un rechargement de page le perd, c'est voulu par le contrat.
  private accessTokenSignal = signal<string | null>(null);
  private principalSignal = signal<Principal | null>(null);

  readonly principal = this.principalSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.principalSignal() !== null);

  private rotation$?: Observable<TokenResponse>;

  getAccessToken(): string | null {
    return this.accessTokenSignal();
  }

  private setSession(response: TokenResponse): void {
    this.accessTokenSignal.set(response.access_token);
    this.principalSignal.set(response.principal);
  }

  clearSession(): void {
    this.accessTokenSignal.set(null);
    this.principalSignal.set(null);
  }

  login(credentials: LoginRequest): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/login`, credentials, { withCredentials: true })
      .pipe(tap((response) => this.setSession(response)));
  }

  // Un seul rafraîchissement en vol à la fois, partagé entre tous les
  // appelants (sinon le serveur révoque toute la session sur des rotations concurrentes).
  refreshShared(): Observable<TokenResponse> {
    this.rotation$ ??= this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/refresh`, {}, { withCredentials: true })
      .pipe(
        tap((response) => this.setSession(response)),
        finalize(() => (this.rotation$ = undefined)),
        shareReplay(1)
      );
    return this.rotation$;
  }

  logout(): Observable<void> {
    return this.http
      .post<void>(`${environment.apiUrl}/auth/logout`, {}, { withCredentials: true })
      .pipe(tap(() => this.clearSession()));
  }

  changePassword(payload: PasswordChangeRequest): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/password`, payload, { withCredentials: true })
      .pipe(tap((response) => this.setSession(response)));
  }

  me(): Observable<Principal> {
    return this.http.get<Principal>(`${environment.apiUrl}/auth/me`);
  }
}
