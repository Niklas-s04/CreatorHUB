# Design System

## Purpose

This document describes the shared UI patterns used by CreatorHUB. It is the reference for spacing, typography, colors, state handling, and accessible interaction patterns.

## Component Inventory

### Layout and Navigation

- `TopBar` for global search, notifications, and profile actions
- `Sidebar` for primary navigation
- `Breadcrumbs` for route context
- `PageHeader` for page-level titles and actions

### Status and Feedback

- `GlobalLoading` for page-level loading states
- `Skeleton` and `ListSkeleton` for fetch placeholders
- `EmptyState` for empty data sets
- `ErrorState` for retryable errors
- `InlineHint` for contextual messages
- `ToastProvider` for global success and error feedback

### Domain-Specific UI

- Product views
- Asset library views
- Content workflow views
- Email thread views
- Operations inbox views
- Audit views
- Admin views
- Settings views

## Button Standards

- Base class: `.btn`
- Variants: `.primary`, `.secondary`, `.danger`, `.ghost`
- Interactive states must cover hover, active, focus-visible, and disabled
- Disabled buttons must remain visually distinct and semantically disabled

## Form Controls

- Every input should have a label or a clear accessible name
- Error states should use `aria-invalid` and `aria-describedby`
- Validation messages should be visible and screen-reader friendly

## Tables

- Use semantic table markup with `caption` and scoped headers
- Sortable columns should expose `aria-sort`
- Empty states should be consistent and readable

## Modals and Drawers

- Use `role="dialog"` and `aria-modal="true"`
- Trap focus while open
- Close on Escape where appropriate
- Return focus to the triggering element after close

## Spacing

Defined spacing tokens:

- `--space-1: 4px`
- `--space-2: 8px`
- `--space-3: 12px`
- `--space-4: 16px`
- `--space-5: 20px`
- `--space-6: 24px`
- `--space-8: 32px`

Rule:

- Prefer tokens over hardcoded spacing values.

## Typography

- Base text should use the shared typography tokens.
- Headings should follow the same scale across pages.
- Secondary text should use the muted text token instead of custom colors.

## Color System

Core tokens:

- `--bg`
- `--panel`
- `--panel2`
- `--text`
- `--muted`
- `--accent`
- `--ok`
- `--warn`
- `--danger`

Rule:

- Do not introduce hardcoded colors without extending the token set.

## Interaction Rules

- All interactive elements must be reachable by keyboard
- Focus must be visible
- Escape should close overlays such as drawers and dialogs
- Live regions should be used for meaningful async status changes

## State Handling

- Loading should be represented explicitly
- Success should be confirmed with visible feedback
- Errors should be actionable and close to the affected control
- Empty states should offer a next step when possible

## Source of Truth

- Styling and tokens: `frontend/src/styles.css`
- Shared state components: `frontend/src/shared/ui/states/*`
- Shared layout components: `frontend/src/shared/ui/layout/*`
