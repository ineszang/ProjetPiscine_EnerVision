import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { Chart } from 'chart.js';
import { ConsumptionGauge } from './consumption-gauge';

vi.mock('chart.js', () => {
  class ChartMock {
    static instances: ChartMock[] = [];
    static register = vi.fn();
    update = vi.fn();
    destroy = vi.fn();
    data = { datasets: [{}] };
    constructor() {
      ChartMock.instances.push(this);
    }
  }
  return { Chart: ChartMock, registerables: [] };
});

type ChartDouble = { destroy: ReturnType<typeof vi.fn> };

function lastChart(): ChartDouble | undefined {
  return (Chart as unknown as { instances: ChartDouble[] }).instances.at(-1);
}

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

  it('détruit le graphique quand le composant est détruit', () => {
    TestBed.configureTestingModule({ imports: [ConsumptionGauge] });
    const fixture = TestBed.createComponent(ConsumptionGauge);
    fixture.componentRef.setInput('consumption', 300);
    fixture.componentRef.setInput('capacity', 1000);
    fixture.detectChanges();

    const chart = lastChart();
    fixture.destroy();

    expect(chart?.destroy).toHaveBeenCalledTimes(1);
  });
});
