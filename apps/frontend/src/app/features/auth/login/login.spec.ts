import { TestBed } from '@angular/core/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { Login } from './login';
import { AuthService } from '../../../core/services/auth.service';
import { MOTIF_LIEN_RESET_INVALIDE } from '../../../shared/models/auth-redirect-reason';

function configure(queryParams: Record<string, string> = {}) {
  const authMock = { login: vi.fn() };
  const routerMock = { navigate: vi.fn() };

  return {
    authMock,
    routerMock,
    testBed: TestBed.configureTestingModule({
      imports: [Login, ReactiveFormsModule],
      providers: [
        { provide: AuthService, useValue: authMock },
        { provide: Router, useValue: routerMock },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap(queryParams) } },
        },
      ],
    }),
  };
}

describe('Login', () => {
  let authMock: { login: ReturnType<typeof vi.fn> };
  let routerMock: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    const attirail = configure();
    authMock = attirail.authMock;
    routerMock = attirail.routerMock;
    await attirail.testBed.compileComponents();
  });

  it('ne soumet pas si le formulaire est invalide', () => {
    const fixture = TestBed.createComponent(Login);
    fixture.componentInstance.onSubmit();
    expect(authMock.login).not.toHaveBeenCalled();
  });

  it('redirige vers /change-password si must_change_password est vrai', () => {
    const fixture = TestBed.createComponent(Login);
    const component = fixture.componentInstance;
    component.form.setValue({ email: 'a@a.com', password: 'secret' });

    authMock.login.mockReturnValue(of({ principal: { role: 'admin', must_change_password: true } }));

    component.onSubmit();
    expect(routerMock.navigate).toHaveBeenCalledWith(['/change-password']);
  });

  it('redirige vers /dashboard si le mot de passe est déjà à jour', () => {
    const fixture = TestBed.createComponent(Login);
    const component = fixture.componentInstance;
    component.form.setValue({ email: 'a@a.com', password: 'secret' });

    authMock.login.mockReturnValue(of({ principal: { role: 'lecteur', must_change_password: false } }));

    component.onSubmit();
    expect(routerMock.navigate).toHaveBeenCalledWith(['/dashboard']);
  });

  it('affiche un message générique sur un 401', () => {
  const fixture = TestBed.createComponent(Login);
  const component = fixture.componentInstance;
  component.form.setValue({ email: 'a@a.com', password: 'wrong' });

  authMock.login.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 401 })));

  component.onSubmit();
  fixture.detectChanges(); // rend le bloc @if (errorMessage()) du template

  expect(component.errorMessage()).toBe('Email ou mot de passe incorrect.');
  const errorEl = fixture.nativeElement.querySelector('.ev-alert');
  expect(errorEl?.textContent).toContain('Email ou mot de passe incorrect.');
  });

  it("affiche le délai d'attente sur un 429 avec Retry-After", () => {
    const fixture = TestBed.createComponent(Login);
    const component = fixture.componentInstance;
    component.form.setValue({ email: 'a@a.com', password: 'wrong' });

    authMock.login.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 429, headers: new HttpHeaders({ 'Retry-After': '30' }) }))
    );

    component.onSubmit();
    fixture.detectChanges(); // rend aussi le sous-bloc @if (retryAfterSeconds(); as seconds)

    expect(component.retryAfterSeconds()).toBe(30);
    const errorEl = fixture.nativeElement.querySelector('.ev-alert');
    expect(errorEl?.textContent).toContain('30s');
  });

  it('affiche le message standard quand on arrive avec ?motif=lien-expire', async () => {
    const attirail = configure({ motif: MOTIF_LIEN_RESET_INVALIDE });
    await attirail.testBed.compileComponents();
    const fixture = TestBed.createComponent(Login);

    expect(fixture.componentInstance.errorMessage()).toContain('expiré');
  });

  it('désactive le bouton tant que le formulaire est invalide', () => {
    const fixture = TestBed.createComponent(Login);
    fixture.detectChanges();

    const button = fixture.nativeElement.querySelector('button[type="submit"]');
    expect(button.disabled).toBe(true);
    expect(fixture.nativeElement.querySelector('.ev-alert')).toBeNull();
  });

 it('déclenche onSubmit via la soumission réelle du formulaire (ngSubmit)', () => {
  const fixture = TestBed.createComponent(Login);
  const component = fixture.componentInstance;
  component.form.setValue({ email: 'a@a.com', password: 'secret' });
  fixture.detectChanges();

  authMock.login.mockReturnValue(of({ principal: { role: 'lecteur', must_change_password: false } }));

  const form = fixture.nativeElement.querySelector('form');
  form.dispatchEvent(new Event('submit'));
  fixture.detectChanges();

  expect(authMock.login).toHaveBeenCalledWith({ email: 'a@a.com', password: 'secret' });
  });
});
