import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Card } from '../../../shared/components/ui/card/card';

@Component({
  selector: 'app-site-detail-placeholder',
  standalone: true,
  imports: [Card],
  templateUrl: './site-detail-placeholder.html',
  styleUrl: './site-detail-placeholder.scss',
})
export class SiteDetailPlaceholder {
  private route = inject(ActivatedRoute);

  siteId = this.route.snapshot.paramMap.get('siteId');
}
