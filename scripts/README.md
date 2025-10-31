# Scripts

Data ingestion and maintenance scripts live here.

## Prerequisites

- Python 3.10+
- Local internet access (the hosted sandbox blocks outbound calls)
- Optional scraper dependencies (install once):
  ```bash
  pip install -r scripts/requirements.txt
  ```

## Updating Drinkware Data

1. Scrape the catalogue:
   ```bash
   python scripts/scrape_zus_drinkware.py --output db/raw/products.json
   ```
   - Uses the Shopify JSON endpoints; no browser required.
   - Adjust `--collection` or `--max-pages` as needed.
2. Build the FAISS index + metadata consumed by the backend:
   ```bash
   python scripts/ingest_products.py --input-file db/raw/products.json --output-dir db/faiss
   ```

## Updating Outlet Data

1. Scrape the outlet listings (requires Chrome + Selenium WebDriver):
   ```bash
   python scripts/scrape_zus_outlets.py --output db/raw/outlets.json
   ```
   - The script launches a headless Chrome instance, so ensure Google Chrome is installed.
   - Use `--max-pages` if you want to limit pagination.
2. _(Optional)_ Enrich the scraped JSON with latitude/longitude pulled from the `map_url` short links:
   ```bash
   python scripts/enrich_outlets_geo.py --input db/raw/outlets.json --overwrite
   ```
   - Resolves Google Maps URLs and updates `latitude` / `longitude` fields where missing.
   - Use `--output` instead of `--overwrite` to write to a separate file.
3. Sync the scraped (and optionally enriched) JSON into the SQLite database used by the API:
   ```bash
   python scripts/sync_outlets.py --input-file db/raw/outlets.json --database db/outlets.db --drop-existing
   ```
   - `--drop-existing` replaces the previous table contents.

## After Refreshing Data

- Commit the regenerated assets (`db/outlets.db`, `db/faiss/products.index`, `db/faiss/products_metadata.json`) if you want them baked into deployments.
- When deploying to Railway, the backend seeds `/app/db` with these files on first start and exposes their readiness via `/ready`.
