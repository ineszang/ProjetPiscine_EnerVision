import { FormControl } from '@angular/forms';
import { passwordValidators } from './password.validator';

function estValide(motDePasse: string): boolean {
  return new FormControl(motDePasse, passwordValidators).valid;
}

describe('passwordValidators', () => {
  it('accepte un mot de passe couvrant les quatre classes', () => {
    expect(estValide('Un-mot-de-passe1!')).toBe(true);
  });

  it('accepte un mot de passe accentué (alignement avec le backend, ex: "Sécurité1")', () => {
    expect(estValide('Sécurité1!')).toBe(true);
  });

  it('refuse un mot de passe sans majuscule même avec un "×" ou un "÷"', () => {
    expect(estValide('abcdefg1×')).toBe(false);
    expect(estValide('abcdefg1÷')).toBe(false);
  });

  it('refuse un mot de passe sans minuscule même avec un "×" ou un "÷"', () => {
    expect(estValide('ABCDEFG1×')).toBe(false);
    expect(estValide('ABCDEFG1÷')).toBe(false);
  });
});
