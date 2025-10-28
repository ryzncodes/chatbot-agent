# Scripts

Data ingestion and maintenance scripts live here:

- `ingest_products.py` — converts drinkware JSON exports into a FAISS index + metadata.
- `sync_outlets.py` — loads outlet JSON into the SQLite database.
- `scrape_zus_drinkware.py` — helper to scrape the drinkware catalogue (run locally with internet access).

Optional scraper dependencies: `pip install -r scripts/requirements.txt`.
