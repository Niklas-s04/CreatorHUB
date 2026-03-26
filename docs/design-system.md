# Design System – CreatorHUB

Stand: 26.03.2026

## 1) Komponenten-Inventar

### Layout & Navigation
- `TopBar` – globale Suche, Benachrichtigungen, Profil
- `Sidebar` – Hauptnavigation (Desktop + Drawer auf Mobile)
- `Breadcrumbs` – Kontextnavigation je Route
- `PageHeader` – Titel/Subtitel/Aktionsbereich pro Seite

### Zustände & Feedback
- `GlobalLoading` – initiale/seitige Ladezustände
- `ListSkeleton` / `Skeleton` – Platzhalter während Fetch
- `EmptyState` – leere Datenzustände
- `ErrorState` – Fehlerkarten mit Retry
- `InlineHint` – Inline-Hinweise (Domain/Technical/Warning/Success/Error)
- `ToastProvider` – globales Feedback (polite success, assertive error)

### Domain-nahe UI (Feature-spezifisch)
- Produktliste/-detail, Assets-Library, Content-Kanban, E-Mail-Threads, Operations Inbox, Audit, Admin, Settings

## 2) Standards pro Baustein

### Buttons
- Basis: `.btn`; Varianten: `.primary`, `.secondary`, `.danger`, `.ghost`
- Interaktive Zustände: `:hover`, `:active`, `:focus-visible`
- Disabled: `button[disabled]` mit reduzierter Opazität und `cursor:not-allowed`
- Loading: optional `.is-loading`

### Inputs / Selects / Textareas
- Immer mit Label (`label[for]`) oder `aria-label` (nur wenn visuell nötig)
- Fehlerzustand: `aria-invalid`, `aria-describedby`, Fehlertext mit `role="alert"`
- Fokus sichtbar über globales `:focus-visible` Pattern

### Tabellen
- Semantik: `caption`, `th scope="col"`, ggf. `th scope="row"`
- Sortierbare Header: `aria-sort` + beschriftete Sortierbuttons
- Leere Tabellenzustände konsistent (eine Zeile mit `colSpan` + `muted`)

### Badges / Pills
- Kleine Statusmarker mit `.pill` oder `.status-badge`
- Farbsemantik über vorhandene Tokens (`ok`, `warn`, `danger`)

### Modals / Drawer
- Drawer: `role="dialog"`, `aria-modal`, Fokusfalle, Escape-Schließen, Fokus-Rückgabe
- Modal-Basisklassen in CSS: `.modal-backdrop`, `.modal`
- Overlay schließt nur via expliziter Interaktion (`button` mit Label)

## 3) Spacing-System

Definiert in `:root`:
- `--space-1: 4px`
- `--space-2: 8px`
- `--space-3: 12px`
- `--space-4: 16px`
- `--space-5: 20px`
- `--space-6: 24px`
- `--space-8: 32px`

Regel:
- Komponentenintern bevorzugt Tokens statt fixer Werte
- `--gap` referenziert `--space-5` als Standard-Abstand

## 4) Typografie-Regeln

Definiert in `:root`:
- Größen: `--font-size-xs/sm/md/lg/xl`
- Gewichte: `--font-weight-regular/medium/semibold`

Regel:
- Body basiert auf `--font-size-sm`
- H1/H2/H3 über Token gesteuert
- Sekundärtext nur über `--muted`

## 5) Farbregeln

Core-Tokens:
- Flächen: `--bg`, `--panel`, `--panel2`
- Text: `--text`, `--muted`
- Interaktion/Brand: `--accent`
- Status: `--ok`, `--warn`, `--danger`, `--violet`

State-Flächen:
- Erfolg: `--state-success-bg/border`
- Fehler: `--state-error-bg/border`
- Warnung: `--state-warning-bg/border`

Regel:
- Keine neuen Hardcoded-Farben ohne Token-Erweiterung

## 6) Interaktionsmuster

- Tastatur-first: alle interaktiven Elemente fokussierbar und per Enter/Space auslösbar
- Fokus klar sichtbar via globales `:focus-visible`
- Dynamische Suche als Combobox/Listbox mit `aria-activedescendant`
- Escape schließt Overlay-UI (Drawer/Modal)

## 7) Zustandsstandardisierung

- Disabled: visuell + semantisch (`disabled` Attribut)
- Loading: Skeleton oder Statusrolle (`role="status"`, `aria-live="polite"`)
- Success: Toast/InlineHint mit Erfolgstonalität
- Error: `ErrorState`, `InlineHint error`, Toast `role="alert"`

## 8) Empty States & Inline-Hinweise

- `EmptyState`: konsistente Karte mit Titel, Nachricht, optional Action
- `InlineHint`: standardisierte Varianten (`domain|technical|success|warning|error`)
- Fehler in Formularen immer feldnah und screenreader-fähig

## 9) Wiederverwendbare UI-Bausteine (Doku-Setup)

Single Source of Truth:
- Styling + Tokens: `frontend/src/styles.css`
- Basis-Zustandskomponenten: `frontend/src/shared/ui/states/*`
- Layout-Grundbausteine: `frontend/src/shared/ui/layout/*`, `page/PageHeader.tsx`

Pflegeprozess:
1. Neue UI zuerst als wiederverwendbare Komponente in `shared/ui` prüfen.
2. Variante über bestehende Tokens/Klassen lösen, nicht ad hoc.
3. A11y-Minimum (Label, Fokus, Keyboard, Live Region) immer in der Komponente verankern.
4. Diese Doku bei neuen Variants/Patterns aktualisieren.