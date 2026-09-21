import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Badge } from './badge';

@Component({
  standalone: true,
  imports: [Badge],
  template: `<ev-badge tone="danger">critique</ev-badge>`,
})
class BadgeHost {}

describe('Badge', () => {
  it('applique le ton neutral par défaut', async () => {
    await TestBed.configureTestingModule({ imports: [Badge] }).compileComponents();
    const fixture = TestBed.createComponent(Badge);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.ev-badge').classList).toContain('ev-badge--neutral');
  });

  it('applique le ton demandé et projette le contenu', async () => {
    await TestBed.configureTestingModule({ imports: [BadgeHost] }).compileComponents();
    const fixture = TestBed.createComponent(BadgeHost);
    fixture.detectChanges();

    const el = fixture.nativeElement.querySelector('.ev-badge');
    expect(el.classList).toContain('ev-badge--danger');
    expect(el.textContent).toContain('critique');
  });
});
