# Pin to bookworm (Debian 12): Playwright 1.48's `install --with-deps` doesn't
# recognise Debian 13 (trixie, now the default `slim` tag) and fails resolving
# obsolete font packages (ttf-unifont / ttf-ubuntu-font-family).
FROM python:3.12-slim-bookworm

# Install Node.js (LTS) for Playwright test execution
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Prebuild a Playwright workspace so test execution never runs `npm install` at
# request time (slow/flaky on small hosts — it left the execution section
# unrendered). @playwright/test + the chromium browser are installed here once,
# and the app reuses this dir via PLAYWRIGHT_WORKDIR.
ENV PLAYWRIGHT_WORKDIR=/opt/pw
RUN mkdir -p $PLAYWRIGHT_WORKDIR \
    && cd $PLAYWRIGHT_WORKDIR \
    && npm init -y >/dev/null 2>&1 \
    && npm install --no-audit --no-fund @playwright/test@1.48.2 \
    && npx playwright install --with-deps chromium

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY VERSION .
COPY agents/ ./agents/
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
