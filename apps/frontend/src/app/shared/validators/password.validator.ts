import { Validators } from '@angular/forms';

export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;
export const PASSWORD_HINT =
  '8 à 128 caractères, avec au moins 1 majuscule, 1 minuscule, 1 chiffre et 1 caractère spécial';

const PASSWORD_PATTERN = /^(?=.*[A-ZÀ-Ý])(?=.*[a-zà-ÿ])(?=.*\d)(?=.*[^\w\s]).*$/;

export const passwordValidators = [
  Validators.required,
  Validators.minLength(PASSWORD_MIN_LENGTH),
  Validators.maxLength(PASSWORD_MAX_LENGTH),
  Validators.pattern(PASSWORD_PATTERN),
];
