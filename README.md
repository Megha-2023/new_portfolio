# Megha Panchal — Professional Portfolio

A bilingual English/French, framework-free portfolio presenting two complementary professional practices: computer-science education and Python/backend software engineering. MLOps remains supporting technical expertise rather than the primary commercial identity.

## Architecture

The public site is a multi-page static website designed for GitHub Pages and the custom domain `https://megha-panchal.fr/`. It uses semantic HTML, one shared CSS system, vanilla JavaScript and directory-based routes. No frontend build step or client-side router is required.

```text
GitHub Pages frontend
        |
        | JSON over HTTPS
        v
FastAPI contact API on Render
        |
        +--> Supabase PostgreSQL
        +--> Gmail API owner notifications
```

### Public routes

- `/` — concise dual-profile homepage
- `/teaching/` — modules, pedagogy, course organisation, leadership and publications
- `/teaching/introduction/` — configurable teaching-video page
- `/projects/` — selected technical work
- `/projects/road-accident-mlops/`
- `/projects/django-aws/`
- `/projects/airflow-weather/`
- `/projects/bentoml-admission/`
- `/journey/` — professional timeline and CV overview
- `/contact/` — bilingual contact form
- `/privacy.html` and `/terms.html` — bilingual legal pages

## Frontend

- `styles.css` contains the established navy/ivory editorial system and shared multi-page components.
- `script.js` provides EN/FR switching, `preferred-language` persistence, responsive navigation, safe configured links, video/CV configuration, privacy-dialog behavior and contact submission.
- `config.js` contains public runtime URLs only. Set `teachingVideoUrl` when the final YouTube/Vimeo video is available and `cvUrl` when a real CV file is added.
- All nested routes use root-relative links for the production custom domain.

## Contact system

The contact page sends JSON to `window.PORTFOLIO_CONFIG.contactApiUrl`, currently `https://api.megha-panchal.fr/api/contact`. The frontend contract remains:

- `name`
- `email`
- `enquiry_type`
- `message`
- `language`
- `privacy_acknowledgement`
- honeypot `website`

The independent FastAPI backend validates submissions, applies a five-per-hour salted-IP rate limit, stores accepted enquiries in Supabase, then attempts an owner notification through the Gmail API. Storage succeeds independently of notification delivery.

See [`backend/README.md`](backend/README.md) for Supabase, Gmail OAuth, Docker and Render setup.

## Local development

Serve the repository root through an HTTP server so directory routes resolve correctly. For example:

```powershell
python -m http.server 5500
```

Run the backend separately from `backend/` or with Docker Compose after creating the ignored `backend/.env`.

## Validation

```powershell
node --check script.js
cd backend
python -B -m pytest -q -p no:cacheprovider
```

The repository does not contain frontend secrets, analytics or advertising cookies.
