import { TestBed } from '@angular/core/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { ForgotPassword } from './forgot-password';
import { AuthService } from '../../../core/services/auth.service';

describe('ForgotPassword', () => {
  let authMock: { forgotPassword: ReturnType<typeof vi.fn> };
  let routerMock: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    authMock = { forgotPassword: vi.fn() };
    routerMock = { navigate: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [ForgotPassword, ReactiveFormsModule],
      providers: [
        { provide: AuthService, useValue: authMock },
        { provide: Router, useValue: routerMock },
        { provide: ActivatedRoute, useValue: {} },
      ],
    }).compileComponents();
  });

  it('ne soumet pas si le formulaire est invalide', () => {
    const fixture = TestBed.createComponent(ForgotPassword);
    fixture.componentInstance.onSubmit();
    expect(authMock.forgotPassword).not.toHaveBeenCalled();
  });

  it('affiche le message générique après une soumission réussie', () => {
    const fixture = TestBed.createComponent(ForgotPassword);
    const component = fixture.componentInstance;
    component.form.setValue({ email: 'operateur@enervision.fr' });
    authMock.forgotPassword.mockReturnValue(of(undefined));

    component.onSubmit();

    expect(component.submitted()).toBe(true);
  });

  it('affiche le même message générique même quand le serveur répond une erreur autre que 429', () => {
    const fixture = TestBed.createComponent(ForgotPassword);
    const component = fixture.componentInstance;
    component.form.setValue({ email: 'inconnu@enervision.fr' });
    authMock.forgotPassword.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 })));

    component.onSubmit();

    expect(component.submitted()).toBe(true);
  });

  it('affiche le délai à respecter quand le taux limite est atteint', () => {
    const fixture = TestBed.createComponent(ForgotPassword);
    const component = fixture.componentInstance;
    component.form.setValue({ email: 'operateur@enervision.fr' });
    authMock.forgotPassword.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 429,
            headers: new HttpHeaders({ 'Retry-After': '900' }),
          })
      )
    );

    component.onSubmit();

    expect(component.submitted()).toBe(false);
    expect(component.retryAfterSeconds()).toBe(900);
  });
});
