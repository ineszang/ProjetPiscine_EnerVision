import { TestBed } from '@angular/core/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { ChangePassword } from './change-password';
import { AuthService } from '../../../core/services/auth.service';

describe('ChangePassword', () => {
  let authMock: { changePassword: ReturnType<typeof vi.fn> };
  let routerMock: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    authMock = { changePassword: vi.fn() };
    routerMock = { navigate: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [ChangePassword, ReactiveFormsModule],
      providers: [
        { provide: AuthService, useValue: authMock },
        { provide: Router, useValue: routerMock },
      ],
    }).compileComponents();
  });

  it('ne soumet pas si le formulaire est invalide (mot de passe trop court)', () => {
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    component.form.setValue({ current_password: 'old', new_password: 'trop-court' });

    component.onSubmit();
    expect(authMock.changePassword).not.toHaveBeenCalled();
  });

  it('redirige vers /dashboard après un changement réussi', () => {
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    component.form.setValue({ current_password: 'ancien-mot-de-passe', new_password: 'un-nouveau-mot-de-passe-valide' });

    authMock.changePassword.mockReturnValue(of({ principal: { role: 'admin' } }));

    component.onSubmit();
    expect(routerMock.navigate).toHaveBeenCalledWith(['/dashboard']);
  });

  it("affiche un message d'erreur si le mot de passe actuel est incorrect", () => {
  const fixture = TestBed.createComponent(ChangePassword);
  const component = fixture.componentInstance;
  component.form.setValue({ current_password: 'mauvais-mot-de-passe', new_password: 'un-nouveau-mot-de-passe-valide' });

  authMock.changePassword.mockReturnValue(throwError(() => new Error('401')));

  component.onSubmit();
  fixture.detectChanges(); // rend le bloc @if (errorMessage())

  expect(component.errorMessage()).toContain('incorrect');
  const errorEl = fixture.nativeElement.querySelector('.ev-alert');
  expect(errorEl?.textContent).toContain('incorrect');
  });

  it('désactive le bouton tant que le formulaire est invalide', () => {
  const fixture = TestBed.createComponent(ChangePassword);
  fixture.detectChanges();

  const button = fixture.nativeElement.querySelector('button[type="submit"]');
  expect(button.disabled).toBe(true);
  expect(fixture.nativeElement.querySelector('.ev-alert')).toBeNull();
  });

  it('déclenche onSubmit via la soumission réelle du formulaire (ngSubmit)', () => {
  const fixture = TestBed.createComponent(ChangePassword);
  const component = fixture.componentInstance;
  component.form.setValue({ current_password: 'ancien-mot-de-passe', new_password: 'un-nouveau-mot-de-passe-valide' });
  fixture.detectChanges();

  authMock.changePassword.mockReturnValue(of({ principal: { role: 'admin' } }));

  const form = fixture.nativeElement.querySelector('form');
  form.dispatchEvent(new Event('submit'));
  fixture.detectChanges();

  expect(authMock.changePassword).toHaveBeenCalledWith({
    current_password: 'ancien-mot-de-passe',
    new_password: 'un-nouveau-mot-de-passe-valide',
  });
});

});
