# Official Playwright image ships Node.js + all browsers + system deps.
# Pin the tag to the same Playwright version as package.json.
FROM mcr.microsoft.com/playwright:v1.48.2-jammy

WORKDIR /runner

# Install deps first for layer caching.
COPY package.json ./
RUN npm install --no-audit --no-fund

COPY server.js ./

# The generated specs are written next to server.js and run from here.
ENV RUNNER_WORKSPACE=/runner
ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
