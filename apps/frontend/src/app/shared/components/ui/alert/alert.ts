import { Component, HostBinding, input } from '@angular/core';

export type AlertSeverity = 'success' | 'warning' | 'danger';

@Component({
  selector: 'ev-alert',
  standalone: true,
  templateUrl: './alert.html',
  styleUrl: './alert.scss',
})
export class Alert {
  severity = input<AlertSeverity>('danger');

  @HostBinding('class')
  get hostClass(): string {
    return `ev-alert ev-alert--${this.severity()}`;
  }

  @HostBinding('attr.role')
  readonly role = 'alert';
}
