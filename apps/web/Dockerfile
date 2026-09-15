FROM node:22-alpine AS dependencies
WORKDIR /opt/vai
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci

FROM dependencies AS builder
ARG NEXT_PUBLIC_VAI_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_VAI_API_URL=${NEXT_PUBLIC_VAI_API_URL}
COPY apps/web apps/web
RUN npm run build:web

FROM node:22-alpine AS runtime
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /opt/vai
COPY --from=builder /opt/vai/package.json /opt/vai/package-lock.json ./
COPY --from=builder /opt/vai/node_modules node_modules
COPY --from=builder /opt/vai/apps/web apps/web
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "@vai/web"]
