# API Design Guidelines

## Versioning

- Stable API routes live under `/api/v1/...`.
- Legacy routes under `/api/...` remain available for compatibility and are marked as deprecated in OpenAPI.

## Project Hub

- `GET /api/v1/projects` supports `q`, `status`, `category_id`, `preview_status`,
  `due_before`, `attention_only`, pagination, and sorting.
- `POST /api/v1/projects` can include `content_item_ids` and `product_ids`.
- `GET|PATCH|DELETE /api/v1/projects/{project_id}` manages the project record.
- `POST|DELETE /api/v1/projects/{project_id}/content/{content_item_id}` manages an
  existing content relation.
- `POST /api/v1/projects/{project_id}/content` creates and links content atomically at
  the workflow level.
- Product relations follow the same pattern under `/products`.
- Category management is available under `/api/v1/projects/categories`.

## Error Format

All error responses use a shared envelope:

```json
{
  "code": "NOT_FOUND",
  "message": "Product not found",
  "status": 404,
  "details": null
}
```

- `code` is a stable machine-readable identifier.
- `message` is short, human-readable, and suitable for UI display.
- `status` matches the HTTP status code.
- `details` contains structured validation or diagnostic data when available.

## Pagination and Sorting

List endpoints use a consistent query contract:

- `limit` as an integer greater than or equal to 1
- `offset` as an integer greater than or equal to 0
- `sort_by` as a field name
- `sort_order` as `asc` or `desc`

Responses return a consistent envelope:

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

Domain-specific filters such as `status`, `owner_type`, or `search` may be added per route, but pagination and sorting stay consistent.

## OpenAPI

- Tags and route descriptions are defined centrally in the application configuration.
- Common error responses for 400, 401, 403, 404, 409, 422, 500, and 503 should be documented globally.
