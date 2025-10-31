# Frontend

Vite + React client that renders the conversational UI, planner timeline, and unhappy-flow indicators for the ZUS AI Assistant.

## Quickstart

```bash
npm install
npm run dev
```

The development server runs at `http://localhost:5173`. Set `VITE_API_URL` in a `.env` file to point at your backend (defaults to `http://localhost:8000`).

## Project Structure

- `src/components/` — chat layout, quick command chips, and autocomplete hints.
- `src/state/` — persisted Zustand store for messages, slots, and planner events.
- `src/services/` — REST client wrappers for chat, tools, and metrics endpoints.
- `src/styles/` — shared theme tokens and global styles.

## Testing

Build and lint the project via:

```bash
npm run build
```

Execute Cypress end-to-end specs with:

```bash
npm run test:e2e
```
