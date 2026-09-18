import { Component, computed, input } from '@angular/core';
import { PASSWORD_REQUIREMENTS } from '../../validators/password.validator';

@Component({
  selector: 'app-password-requirements',
  standalone: true,
  templateUrl: './password-requirements.html',
  styleUrl: './password-requirements.scss',
})
export class PasswordRequirementsChecklist {
  password = input('');

  requirements = computed(() =>
    PASSWORD_REQUIREMENTS.map((requirement) => ({
      label: requirement.label,
      met: requirement.test(this.password()),
    })),
  );
}
