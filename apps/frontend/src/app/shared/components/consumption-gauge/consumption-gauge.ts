import { Component, ElementRef, ViewChild, input, effect, AfterViewInit } from '@angular/core';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

@Component({
  selector: 'app-consumption-gauge',
  standalone: true,
  templateUrl: './consumption-gauge.html',
  styleUrl: './consumption-gauge.scss',
})
export class ConsumptionGauge implements AfterViewInit {
  consumption = input.required<number>();
  capacity = input.required<number>();

  @ViewChild('canvas') private canvasRef!: ElementRef<HTMLCanvasElement>;
  private chart?: Chart;

  constructor() {
    effect(() => {
      const used = this.consumption();
      const remaining = Math.max(0, this.capacity() - used);
      if (this.chart) {
        this.chart.data.datasets[0].data = [used, remaining];
        this.chart.update('none');
      }
    });
  }

  ngAfterViewInit(): void {
    const used = this.consumption();
    const remaining = Math.max(0, this.capacity() - used);

    this.chart = new Chart(this.canvasRef.nativeElement, {
      type: 'doughnut',
      data: {
        labels: ['Utilisé', 'Disponible'],
        datasets: [
          {
            data: [used, remaining],
            backgroundColor: ['#3b82f6', '#e5e7eb'],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        animation: { duration: 300 },
        plugins: { legend: { display: false } },
      },
    });
  }
}
