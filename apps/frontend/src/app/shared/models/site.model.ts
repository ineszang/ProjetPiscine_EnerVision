export interface Site {
  site_id: string;
  site_name: string;
  site_type: string;
  location: string | null;
  capacity_kw: number | null;
  status: string | null;
}
