$env:DATABASE_URL="YOUR_REAL_RENDER_DATABASE_URL"
$env:PGSSLMODE="require"

$env:PUBLIC_BASE_URL="http://127.0.0.1:8000"

$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="gherman3879@gmail.com"
$env:SMTP_PASS="YOUR_GMAIL_APP_PASSWORD"
$env:SMTP_FROM_EMAIL="gherman3879@gmail.com"
$env:SMTP_USE_TLS="1"

uvicorn api:app --reload --port 8000
