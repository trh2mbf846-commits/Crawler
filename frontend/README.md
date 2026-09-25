# Ausschreibungs-Crawler – Frontend

Eigenständiges React/Vite/TypeScript-Frontend für das Vergabe-/Ausschreibungs-Suchportal. Der API-Vertrag steht in
[`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md).

## Setup

```bash
npm install
cp .env.example .env   # VITE_API_BASE_URL bei Bedarf anpassen
npm run dev             # http://localhost:5174
```

Der Dev-Server startet auch ohne laufendes Backend; Ladefehler werden als freundliche Fehlermeldung angezeigt statt
die App abstürzen zu lassen.

## Scripts

- `npm run dev` – Dev-Server (Port 5174)
- `npm run build` – Typecheck (`tsc -b`) + Produktions-Build
- `npm run lint` – oxlint
- `npm run preview` – Produktions-Build lokal ausliefern

## Struktur

- `src/api/` – Typen aus dem API-Vertrag (`types.ts`) und der fetch-Client (`client.ts`)
- `src/pages/` – Gesamtübersicht, Detailansicht, Suchprofile, Quellstatus-Dashboard, Entscheidungs-Posteingang
- `src/components/` – wiederverwendbare UI-Bausteine (Badges, Filterleiste, Ranking-Balken, Zeitleiste, …)
- `src/hooks/` – `useAsync` (Laden/Fehler/Reload) und `useDebouncedValue` (Volltextsuche)
- `src/utils/` – Formatierung, Status-/Dringlichkeits-Ableitungen

Styling erfolgt mit Tailwind CSS (siehe `tailwind.config.js`); Akzentfarben sind gezielt auf Dringlichkeit
(rot/gelb) und KI-Relevanz beschränkt.
