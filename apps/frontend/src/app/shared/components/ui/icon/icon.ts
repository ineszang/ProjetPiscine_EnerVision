import { Component, input } from '@angular/core';

export type IconName = 'spike' | 'threshold' | 'anomaly' | 'outage' | 'sensor';

@Component({
  selector: 'ev-icon',
  standalone: true,
  templateUrl: './icon.html',
  styleUrl: './icon.scss',
})
export class Icon {
  name = input.required<IconName>();
  label = input<string | null>(null);
}
