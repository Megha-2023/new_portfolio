# Megha Panchal — Professional Portfolio

A bilingual English/French portfolio presenting Megha Panchal’s two complementary professional practices:

- Python and backend development
- Computer-science teaching and technical training

MLOps appears as complementary technical expertise rather than the primary commercial positioning.

## Live website

> Production URL: **https://megha-panchal.fr/**
> Current GitHub Pages URL: **https://megha-2023.github.io/new_portfolio/**

## Technical overview

The project combines a static, GitHub Pages-compatible frontend with a separately deployed Python contact API.

```text
Browser / GitHub Pages
        |
        | JSON over HTTPS
        v
Python FastAPI contact API
        |
        +--> Supabase PostgreSQL
        |      - private enquiries
        |      - hashed-IP rate limits
        |      - 12-month retention job
        |
        +--> Gmail API over HTTPS
               - owner notifications
               - visitor address used as Reply-To
```

### Frontend

- Semantic HTML, custom CSS and vanilla JavaScript
- Responsive editorial grid and accessible navigation
- English/French interface using a central translation object and `data-i18n` attributes
- Language preference stored locally under `preferred-language`
- Accessible contact validation, privacy dialog and inline confirmation panel
- Runtime API endpoint configured through `config.js`
- No frontend framework, analytics or advertising cookies

### Backend

- Python 3.12
- FastAPI and Pydantic validation
- Supabase Python client for PostgreSQL access
- Gmail API with OAuth 2.0 refresh-token authentication for notification delivery
- CORS allow-list configured through environment variables
- Health endpoint at `GET /health`
- Contact endpoint at `POST /api/contact`
- Protected command for retrying stored but unsent notifications

### Contact security

- All visitor fields are trimmed and validated server-side.
- A hidden honeypot silently accepts automated spam without storing it.
- Requests are limited to five submissions per hashed IP per hour.
- IP addresses are salted with SHA-256; raw IP addresses are never stored.
- Supabase Row Level Security is enabled with no public read or insert policies.
- Only the Python backend receives `SUPABASE_SECRET_KEY`.
- Enquiries are stored before Gmail delivery is attempted.
- Gmail failures retain the enquiry and record a safe notification status.
- Visitor content is HTML-escaped before inclusion in notification emails.
- Ordinary enquiries are automatically deleted after 12 months.

## Repository structure

```text
.
├── index.html                 # Portfolio structure and contact form
├── styles.css                 # Responsive editorial styling
├── script.js                  # Bilingual UI, validation and form behaviour
├── config.js                  # Runtime contact API URL
├── config.example.js          # Frontend configuration example
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI application and routes
│   │   ├── config.py          # Environment configuration
│   │   ├── schemas.py         # Request validation
│   │   ├── security.py        # Client-IP handling and hashing
│   │   ├── database.py        # Supabase persistence
│   │   ├── email_service.py   # Multipart Gmail notifications
│   │   └── retry_notifications.py
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md              # Detailed backend setup and deployment guide
├── supabase/migrations/       # Database schema, RLS and retention job
├── backend/Dockerfile       # Render and local API container image
└── docker-compose.yml       # Local container development
```

## Tests and validation

Backend tests use local fakes and do not contact Supabase or send real email:

```powershell
cd backend
python -B -m pytest -q -p no:cacheprovider
```

Check the frontend JavaScript from the repository root:

```powershell
node --check script.js
```

## Docker

After creating `backend/.env`:

```powershell
docker compose build
docker compose up
```

The API is then available at `http://127.0.0.1:8000`.

## Deployment outline

1. Deploy the static frontend to GitHub Pages.
2. Deploy `backend/Dockerfile` as a Render Docker Web Service.
3. Configure backend secrets through the hosting provider’s environment settings.
4. Apply the Supabase migration to the production project.
5. Add the production portfolio origin to `ALLOWED_ORIGINS`.
6. Keep `config.js` pointed to `https://api.megha-panchal.fr/api/contact`.
7. Configure GitHub Pages and OVH DNS for the production/custom domains.

See [backend/README.md](backend/README.md) for detailed database, Gmail, proxy, deployment and production-testing instructions.

## Privacy

The selected interface language may be stored locally in the visitor’s browser. Contact information is used only to answer professional enquiries. The site does not include analytics or advertising cookies.
