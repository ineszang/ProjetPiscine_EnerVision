import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Card } from '../../../shared/components/ui/card/card';
import { Brand } from '../../../shared/components/ui/brand/brand';

@Component({
  selector: 'app-site-detail-placeholder',
  standalone: true,
  imports: [RouterLink, Card, Brand],
  templateUrl: './site-detail-placeholder.html',
  styleUrl: './site-detail-placeholder.scss',
})
export class SiteDetailPlaceholder {
  private route = inject(ActivatedRoute);

  siteId = this.route.snapshot.paramMap.get('siteId');
}
