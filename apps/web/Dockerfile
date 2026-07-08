# =====================================================
# AI News Scraper — Web (Next.js) Dockerfile
# =====================================================

FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
COPY .npmrc ./.npmrc
COPY apps/web/package.json ./apps/web/
COPY packages/shared/package.json ./packages/shared/
# Install in the same stage as the build: copying ``node_modules`` between
# stages via ``COPY --from=deps`` does not preserve pnpm's internal
# symlinks (``next/dist/bin/next`` resolves through ``.pnpm/...`` which
# Docker does not follow), so ``next build`` fails with
# ``Cannot find module '.../next/dist/bin/next'``. Installing once in the
# builder stage keeps the symlink graph intact. Costs layer caching on
# source changes; acceptable for a thin Next.js app.
RUN pnpm install --frozen-lockfile
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# ``next.config.ts`` reads ``process.env.API_INTERNAL_URL`` at build
# time (not runtime — config is evaluated once during ``next build``
# and the resolved value is baked into the standalone output). Without
# setting it here, the rewrite target falls back to
# ``http://localhost:8082`` which is the web container itself in
# compose, so ``/api/backend/*`` requests return 500 with
# ``ECONNREFUSED``. ``api:8082`` is the compose-network DNS name for
# the ``api`` service. Override via the ``API_INTERNAL_URL`` build arg
# in ``docker-compose.yml`` for non-default networks.
ARG API_INTERNAL_URL=http://api:8082
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
RUN pnpm --filter ai-news-scraper-web build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME="0.0.0.0"
CMD ["node", "apps/web/server.js"]
