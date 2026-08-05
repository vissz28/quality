# Pin to bookworm (Debian 12): Playwright 1.48's `install --with-deps` doesn't
# recognise Debian 13 (trixie, now the default `slim` tag) and fails resolving
# obsolete font packages (ttf-unifont / ttf-ubuntu-font-family).
FROM python:3.12-slim-bookworm

# Node.js + a prebuilt Playwright workspace, in ONE layer so the apt index is
# still present when `playwright install --with-deps` runs its own apt-get
# install (a prior `rm -rf .../apt/lists` left it with no install candidates).
# Prebuilding the workspace means test execution never runs `npm install` at
# request time (slow/flaky on small hosts — it left the execution section
# unrendered). The app reuses this dir via PLAYWRIGHT_WORKDIR.
ENV PLAYWRIGHT_WORKDIR=/opt/pw
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && mkdir -p $PLAYWRIGHT_WORKDIR \
    && cd $PLAYWRIGHT_WORKDIR \
    && npm init -y >/dev/null 2>&1 \
    && npm install --no-audit --no-fund @playwright/test@1.48.2 \
    && npx playwright install --with-deps chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# SonarScanner CLI (bundled JRE) + git, so the bot can scan MRs itself (in-bot
# SonarCloud scanner) — clone the reviewed repo and run sonar-scanner. The
# linux-x64 build ships its own JRE, so no system Java is needed.
ENV SONAR_SCANNER_VERSION=6.2.1.4610
RUN apt-get update \
    && apt-get install -y --no-install-recommends git unzip \
    && curl -fsSLo /tmp/scanner.zip "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VERSION}-linux-x64.zip" \
    && unzip -q /tmp/scanner.zip -d /opt \
    && ln -s "/opt/sonar-scanner-${SONAR_SCANNER_VERSION}-linux-x64/bin/sonar-scanner" /usr/local/bin/sonar-scanner \
    && rm /tmp/scanner.zip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY VERSION .
COPY agents/ ./agents/
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
