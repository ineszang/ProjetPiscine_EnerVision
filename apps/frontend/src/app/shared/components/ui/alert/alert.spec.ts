import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Alert } from './alert';

@Component({
  standalone: true,
  imports: [Alert],
  template: `<ev-alert severity="success">C'est fait</ev-alert>`,
})
class AlertHost {}

describe('Alert', () => {
  it('applique la classe danger par défaut', async () => {
    await TestBed.configureTestingModule({ imports: [Alert] }).compileComponents();
    const fixture = TestBed.createComponent(Alert);
    fixture.detectChanges();

    expect(fixture.nativeElement.classList).toContain('ev-alert--danger');
  });

  it('applique la sévérité demandée et projette le contenu', async () => {
    await TestBed.configureTestingModule({ imports: [AlertHost] }).compileComponents();
    const fixture = TestBed.createComponent(AlertHost);
    fixture.detectChanges();

    const el = fixture.nativeElement.querySelector('.ev-alert');
    expect(el.classList).toContain('ev-alert--success');
    expect(el.textContent).toContain("C'est fait");
  });
});
