FROM node:22-alpine

RUN mkdir -p /app && chown node:node /app
USER node
WORKDIR /app

COPY --chown=node:node apps/web/package.json apps/web/package-lock.json* ./
RUN npm install
COPY --chown=node:node apps/web/ ./

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
