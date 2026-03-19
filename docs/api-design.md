# API Design Konventionen

## Versionierung

- Primäre, stabile API-Endpoints liegen unter `/api/v1/...`.
- Legacy-Endpoints unter `/api/...` bleiben vorübergehend verfügbar, sind aber in OpenAPI als `deprecated` markiert.

## Fehlerformat

Fehlerantworten sind vereinheitlicht:

```json
{
  "code": "NOT_FOUND",
  "message": "Product not found",
  "status": 404,
  "details": null
}
```

- `code` ist ein stabiler maschinenlesbarer Fehlercode.
- `message` ist menschenlesbar.
- `status` entspricht dem HTTP-Status.
- `details` enthält optionale strukturierte Fehlerdetails.

## Pagination, Filter, Sortierung

Listenendpunkte verwenden ein einheitliches Schema:

- Query-Parameter:
  - `limit` (int, >=1)
  - `offset` (int, >=0)
  - `sort_by` (string)
  - `sort_order` (`asc` | `desc`)
- Response-Envelope:

```json
{
  "meta": {
    "limit": 50,
    "offset": 0,
    "total": 123,
    "sort_by": "updated_at",
    "sort_order": "desc"
  },
  "items": []
}
```

Fachdomänenfilter (z. B. `status`, `owner_type`, `search`) sind ergänzend erlaubt, aber Pagination-/Sort-Parameter bleiben konsistent.

## OpenAPI

- Tags und Beschreibungen sind zentral in der App-Konfiguration hinterlegt.
- Standard-Fehlerantworten (400/401/403/404/409/422/500/503) sind global dokumentiert.
