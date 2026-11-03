FROM node:24-alpine

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY --chown=node:node frontend/ .
RUN chown node:node /app
USER node
EXPOSE 3000
CMD ["npm", "run", "dev"]
