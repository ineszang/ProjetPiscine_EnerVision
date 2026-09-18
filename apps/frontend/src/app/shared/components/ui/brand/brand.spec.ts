import { TestBed } from '@angular/core/testing';
import { Brand } from './brand';

describe('Brand', () => {
  it("affiche l'icône et le nom EnerVision", async () => {
    await TestBed.configureTestingModule({ imports: [Brand] }).compileComponents();
    const fixture = TestBed.createComponent(Brand);
    fixture.detectChanges();

    const icon = fixture.nativeElement.querySelector('img.ev-brand__icon');
    expect(icon).toBeTruthy();
    expect(fixture.nativeElement.textContent).toContain('EnerVision');
  });
});
