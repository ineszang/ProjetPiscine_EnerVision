import { TestBed } from '@angular/core/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { ChangePassword } from './change-password';
import { AuthService } from '../../../core/services/auth.service';

const NOUVEAU = 'Un-nouveau-mot-de-passe1!';

describe('ChangePassword', () => {
  let authMock: {
    changePassword: ReturnType<typeof vi.fn>;
    takeProvisionalPassword: ReturnType<typeof vi.fn>;
    principal: ReturnType<typeof signal>;
  };
  let routerMock: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    authMock = {
      changePassword: vi.fn(),
      takeProvisionalPassword: vi.fn().mockReturnValue(null),
      principal: signal({ email: 'johan@enervision.fr' }),
    };
    routerMock = { navigate: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [ChangePassword, ReactiveFormsModule],
      providers: [
        { provide: AuthService, useValue: authMock },
        { provide: Router, useValue: routerMock },
      ],
    }).compileComponents();
  });

  function champActuel(fixture: { nativeElement: HTMLElement }): HTMLInputElement | null {
    return fixture.nativeElement.querySelector('#current_password');
  }

  it('ne soumet pas si le formulaire est invalide (mot de passe trop court)', () => {
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    component.form.setValue({ current_password: 'old', new_password: 'trop-court' });

    component.onSubmit();
    expect(authMock.changePassword).not.toHaveBeenCalled();
  });

  it('ne soumet pas si le mot de passe ne couvre pas les 4 classes de caractères', () => {
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    component.form.setValue({ current_password: 'old', new_password: 'longueur-suffisante-sans-majuscule-ni-chiffre' });

    component.onSubmit();
    expect(authMock.changePassword).not.toHaveBeenCalled();
  });

  it('redirige vers /dashboard après un changement réussi', () => {
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    component.form.setValue({ current_password: 'ancien-mot-de-passe', new_password: NOUVEAU });

    authMock.changePassword.mockReturnValue(of({ principal: { role: 'admin' } }));

    component.onSubmit();
    expect(routerMock.navigate).toHaveBeenCalledWith(['/dashboard']);
  });

  it("demande le mot de passe actuel quand la connexion ne l'a pas transmis (page rechargée)", () => {
    const fixture = TestBed.createComponent(ChangePassword);
    fixture.detectChanges();

    expect(champActuel(fixture)).not.toBeNull();
  });

  it('réutilise le mot de passe provisoire de la connexion sans le redemander', () => {
    authMock.takeProvisionalPassword.mockReturnValue('Provisoire-24-caracteres');
    authMock.changePassword.mockReturnValue(of({ principal: { role: 'admin' } }));
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    expect(champActuel(fixture)).toBeNull();
    component.form.controls.new_password.setValue(NOUVEAU);
    component.onSubmit();

    expect(authMock.changePassword).toHaveBeenCalledWith({
      current_password: 'Provisoire-24-caracteres',
      new_password: NOUVEAU,
    });
  });

  it('associe le formulaire au compte connecté pour les gestionnaires de mots de passe', () => {
    const fixture = TestBed.createComponent(ChangePassword);
    fixture.detectChanges();

    const identifiant = fixture.nativeElement.querySelector('input[autocomplete="username"]');
    expect(identifiant.value).toBe('johan@enervision.fr');
  });

  it('sur un 401, dit que le mot de passe actuel est faux et le redemande', () => {
    authMock.takeProvisionalPassword.mockReturnValue('Provisoire-perime');
    authMock.changePassword.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 401 })),
    );
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    component.form.controls.new_password.setValue(NOUVEAU);

    component.onSubmit();
    fixture.detectChanges();

    expect(component.errorMessage()).toContain('Mot de passe actuel incorrect');
    expect(fixture.nativeElement.querySelector('.ev-alert')?.textContent).toContain('incorrect');
    expect(champActuel(fixture)).not.toBeNull();
    expect(component.form.controls.current_password.value).toBe('');
  });

  it('sur un 422, dit que le nouveau mot de passe ne respecte pas la politique', () => {
    authMock.changePassword.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 422 })),
    );
    const fixture = TestBed.createComponent(ChangePassword);
    const component = fixture.componentInstance;
    component.form.setValue({ current_password: 'ancien-mot-de-passe', new_password: NOUVEAU });

    component.onSubmit();

    expect(component.errorMessage()).toContain('Nouveau mot de passe refusé');
    expect(component.form.controls.current_password.value).toBe('ancien-mot-de-passe');
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
    component.form.setValue({ current_password: 'ancien-mot-de-passe', new_password: NOUVEAU });
    fixture.detectChanges();

    authMock.changePassword.mockReturnValue(of({ principal: { role: 'admin' } }));

    const form = fixture.nativeElement.querySelector('form');
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    expect(authMock.changePassword).toHaveBeenCalledWith({
      current_password: 'ancien-mot-de-passe',
      new_password: NOUVEAU,
    });
  });
});
