import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Card } from './card';

@Component({
  standalone: true,
  imports: [Card],
  template: `<ev-card><p>Contenu</p></ev-card>`,
})
class CardHost {}

describe('Card', () => {
  it('projette son contenu', async () => {
    await TestBed.configureTestingModule({ imports: [CardHost] }).compileComponents();
    const fixture = TestBed.createComponent(CardHost);
    fixture.detectChanges();

    const card = fixture.nativeElement.querySelector('ev-card');
    expect(card).toBeTruthy();
    expect(card.textContent).toContain('Contenu');
  });
});
