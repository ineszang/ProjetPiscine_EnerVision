import {
  Component,
  ElementRef,
  ViewChild,
  input,
  effect,
  AfterViewInit,
  OnDestroy,
} from '@angular/core';
import { Chart, registerables } from 'chart.js';
import { SiteSummary } from '../../models/stats.model';

Chart.register(...registerables);

const QUALITY_COLORS: Record<SiteSummary['data_quality'], string> = {
  good: '#2e7d32',
  partial: '#f9a825',
  degraded: '#ef6c00',
  critical: '#c62828',
};

@Component({
  selector: 'app-site-load-chart',
  standalone: true,
  templateUrl: './site-load-chart.html',
  styleUrl: './site-load-chart.scss',
})
export class SiteLoadChart implements AfterViewInit, OnDestroy {
  sites = input.required<SiteSummary[]>();

  @ViewChild('canvas') private canvasRef!: ElementRef<HTMLCanvasElement>;
  private chart?: Chart;

  constructor() {
    effect(() => {
      const sites = this.sites();
      if (this.chart) {
        this.chart.data.labels = sites.map((s) => s.site_name);
        this.chart.data.datasets[0].data = sites.map((s) => s.load_percent ?? 0);
        this.chart.data.datasets[0].backgroundColor = sites.map(
          (s) => QUALITY_COLORS[s.data_quality],
        );
        this.chart.update('none');
      }
    });
  }

  ngAfterViewInit(): void {
    const sites = this.sites();
    this.chart = new Chart(this.canvasRef.nativeElement, {
      type: 'bar',
      data: {
        labels: sites.map((s) => s.site_name),
        datasets: [
          {
            data: sites.map((s) => s.load_percent ?? 0),
            backgroundColor: sites.map((s) => QUALITY_COLORS[s.data_quality]),
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, max: 100, title: { display: true, text: 'Charge (%)' } },
        },
      },
    });
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }
}
