import { TestBed } from '@angular/core/testing';
import { PasswordRequirementsChecklist } from './password-requirements';

describe('PasswordRequirementsChecklist', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PasswordRequirementsChecklist],
    }).compileComponents();
  });

  it('ne coche aucune règle pour un mot de passe vide', () => {
    const fixture = TestBed.createComponent(PasswordRequirementsChecklist);
    fixture.componentRef.setInput('password', '');
    fixture.detectChanges();

    expect(fixture.componentInstance.requirements().every((r) => !r.met)).toBe(true);
  });

  it('ne coche que les règles satisfaites pour un mot de passe partiel', () => {
    const fixture = TestBed.createComponent(PasswordRequirementsChecklist);
    fixture.componentRef.setInput('password', 'abcdefgh');
    fixture.detectChanges();

    const parLabel = new Map(fixture.componentInstance.requirements().map((r) => [r.label, r.met]));
    expect(parLabel.get('8 caractères minimum')).toBe(true);
    expect(parLabel.get('1 minuscule')).toBe(true);
    expect(parLabel.get('1 majuscule')).toBe(false);
    expect(parLabel.get('1 chiffre')).toBe(false);
    expect(parLabel.get('1 caractère spécial')).toBe(false);
  });

  it('coche toutes les règles pour un mot de passe conforme', () => {
    const fixture = TestBed.createComponent(PasswordRequirementsChecklist);
    fixture.componentRef.setInput('password', 'Un-nouveau-mot-de-passe1!');
    fixture.detectChanges();

    expect(fixture.componentInstance.requirements().every((r) => r.met)).toBe(true);
  });
});
