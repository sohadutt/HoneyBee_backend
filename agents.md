# AI Agent Guidelines & Project Context

## Core Directives
1. **Write Clean, Typed Code:** Always use Python type hints (`-> Response`, `dict[str, Any]`) in the backend and JSDoc/PropTypes/TypeScript in the frontend.
2. **Zero Bloat:** Never create unnecessary functions, wrappers, or abstractions. If a standard library or framework method exists, use it.
3. **Show, Don't Tell:** Minimize code comments. Code must be self-documenting through precise naming conventions. Only comment on complex business logic or workarounds.
4. **Strict Completeness:** When asked to update a file, return the *complete, working file*. Do not use placeholders like `// ... rest of code`.

## Project Architecture
This is a full-stack Portfolio Builder application.
* **Frontend:** React 18, Vite, React Router DOM, Redux Toolkit, Tailwind CSS, Lucide React, shadcn/ui.
* **Backend:** Django 5+, Django REST Framework (DRF), PostgreSQL, Celery (background tasks).
* **Storage:** Vercel Blob (for profile images).
* **Auth:** JWT (SimpleJWT), Google OAuth, and Email OTP verification.

## Frontend Guidelines (React)
* **Naming Conventions:** 
  * Files: PascalCase for components (`WorkSection.jsx`), camelCase for utilities (`functions.js`).
  * Variables/Functions: `camelCase`.
* **State Management:** Use local `useState` for UI toggles and Redux Toolkit slices (`portfolioSlice.js`) for global data and API fetching via `createAsyncThunk`.
* **Data Mapping:** The backend uses `snake_case`, the frontend uses `camelCase`. Always handle the mapping seamlessly at the API boundary or in serializers, never let `snake_case` leak deep into React components.
* **Styling:** Use Tailwind CSS utility classes. Group related classes logically (layout -> spacing -> typography -> colors -> transitions).

## Backend Guidelines (Django/Python)
* **Naming Conventions:** Strict `snake_case` for variables, functions, and file names. `PascalCase` for Classes.
* **Type Hinting:** Enforce strict Python type hints (e.g., `def get_ip(request: Request) -> str | None:`). Use `from __future__ import annotations`.
* **Database Operations:** 
  * Use `@transaction.atomic` for multi-model writes (e.g., saving a portfolio and its related links).
  * Optimize queries using `.select_related()` and `.prefetch_related()`. Avoid N+1 query problems.
  * Use `.update_fields=['field_name']` when calling `.save()` to prevent race conditions.
* **API Responses:** Ensure consistent JSON structures. Always return standard HTTP status codes (`rest_framework.status`).
* **Background Tasks:** Any email sending (OTP) or heavy data processing must be delegated to Celery tasks using `.delay()`.

## Anti-Patterns to Avoid
* **No `any` Types:** Avoid falling back to `Any` or `any` unless absolutely necessary for dynamic JSON payloads.
* **No Inline Styles:** Never use React `style={{}}` unless dynamically calculating dimensions. Use Tailwind.
* **No Deep Nesting:** Return early in functions to avoid deep `if/else` nesting. 
* **No Hardcoding:** Never hardcode environment variables, API URLs, or secrets. Use `import.meta.env` in React and `django.conf.settings` in Python.