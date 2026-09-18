import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Button } from './button';

@Component({
  standalone: true,
  imports: [Button],
  template: `<ev-button>Valider</ev-button>`,
})
class ButtonHost {}

describe('Button', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [Button] }).compileComponents();
  });

  it('applique la classe de la variante primary par défaut', () => {
    const fixture = TestBed.createComponent(Button);
    fixture.detectChanges();

    const button = fixture.nativeElement.querySelector('button');
    expect(button.classList).toContain('ev-button--primary');
  });

  it('applique la classe de la variante demandée', () => {
    const fixture = TestBed.createComponent(Button);
    fixture.componentRef.setInput('variant', 'danger');
    fixture.detectChanges();

    const button = fixture.nativeElement.querySelector('button');
    expect(button.classList).toContain('ev-button--danger');
  });

  it('désactive le bouton natif quand disabled est vrai', () => {
    const fixture = TestBed.createComponent(Button);
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();

    const button = fixture.nativeElement.querySelector('button');
    expect(button.disabled).toBe(true);
  });

  it('projette le contenu', async () => {
    await TestBed.configureTestingModule({ imports: [ButtonHost] }).compileComponents();
    const fixture = TestBed.createComponent(ButtonHost);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('button').textContent).toContain('Valider');
  });
});
