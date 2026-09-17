// Contrainte : `PASSWORD_PATTERN` doit rester identique au validateur Pydantic de
// `app/schemas/auth.py` côté backend (mêmes plages de majuscules/minuscules, excluant
// × et ÷, mêmes chiffres 0-9, même jeu de caractères spéciaux). `\w`/`\d` divergent entre
// JavaScript (ASCII) et Python (Unicode) : une négation aurait accepté ou rejeté un même
// mot de passe différemment d'un côté à l'autre (ex. "Sécurité1").

import { Validators } from '@angular/forms';

export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;
export const PASSWORD_HINT =
  '8 à 128 caractères, avec au moins 1 majuscule, 1 minuscule, 1 chiffre et 1 caractère spécial';

const SPECIAL_CHARACTERS = '!@#$%^&*()\\-_=+[\\]{};:,.?';
const PASSWORD_PATTERN = new RegExp(
  `^(?=.*[A-ZÀ-ÖØ-Þ])(?=.*[a-zà-öø-þ])` +
    `(?=.*[0-9])(?=.*[${SPECIAL_CHARACTERS}]).*$`,
);

export const passwordValidators = [
  Validators.required,
  Validators.minLength(PASSWORD_MIN_LENGTH),
  Validators.maxLength(PASSWORD_MAX_LENGTH),
  Validators.pattern(PASSWORD_PATTERN),
];
