FROM node:20-alpine AS builder

WORKDIR /app

COPY client/package.json client/package-lock.json* ./client/
COPY server/package.json server/package-lock.json* ./server/
COPY package.json ./

RUN cd client && npm install
RUN cd ../server && npm install

COPY . .

RUN cd client && npm run build

FROM node:20-alpine

WORKDIR /app

COPY server/package.json server/package-lock.json* ./
RUN npm install --omit=dev

COPY --from=builder /app/client/dist ./public
COPY server/src ./src
COPY server/tsconfig.json ./

RUN npm install -g typescript && tsc

ENV PORT=3001
ENV DB_PATH=/app/data/bsms.db
ENV CORS_ORIGIN=*

EXPOSE 3001

RUN mkdir -p /app/data

CMD ["node", "dist/index.js"]
