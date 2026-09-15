import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { ConsumptionGauge } from './consumption-gauge';

vi.mock('chart.js', () => {
  class ChartMock {
    update = vi.fn();
    data = { datasets: [{}] };
    static register = vi.fn();
  }
  return { Chart: ChartMock, registerables: [] };
});

describe('ConsumptionGauge', () => {
  it('se crée sans erreur avec des entrées valides', () => {
    TestBed.configureTestingModule({ imports: [ConsumptionGauge] });
    const fixture = TestBed.createComponent(ConsumptionGauge);
    fixture.componentRef.setInput('consumption', 300);
    fixture.componentRef.setInput('capacity', 1000);
    expect(() => fixture.detectChanges()).not.toThrow();
  });
  it('met à jour le graphique quand les valeurs changent après initialisation', () => {
  TestBed.configureTestingModule({ imports: [ConsumptionGauge] });
  const fixture = TestBed.createComponent(ConsumptionGauge);
  fixture.componentRef.setInput('consumption', 300);
  fixture.componentRef.setInput('capacity', 1000);
  fixture.detectChanges(); // déclenche ngAfterViewInit, this.chart existe désormais

  fixture.componentRef.setInput('consumption', 500);
  fixture.detectChanges(); // ré-exécute l'effect, cette fois avec this.chart défini

  expect(() => fixture.detectChanges()).not.toThrow();
});
});
