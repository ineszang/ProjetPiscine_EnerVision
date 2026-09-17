import { Component, input } from '@angular/core';

export type BadgeTone = 'success' | 'warning' | 'danger' | 'neutral';

@Component({
  selector: 'ev-badge',
  standalone: true,
  templateUrl: './badge.html',
  styleUrl: './badge.scss',
})
export class Badge {
  tone = input<BadgeTone>('neutral');
}
