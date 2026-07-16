import express from 'express';
import cors from 'cors';
import { config } from './config';
import { initDatabase, closeDatabase } from './database';
import apiRouter from './routes/api';

const app = express();

app.use(cors({ origin: config.cors.origin }));
app.use(express.json({ limit: '50mb' }));

app.use('/api', apiRouter);

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

const PORT = config.port;

async function start() {
  await initDatabase();

  app.listen(PORT, () => {
    console.log(`BSMS Tracking Server running on http://localhost:${PORT}`);
    console.log(`API endpoint: http://localhost:${PORT}/api`);
  });

  process.on('SIGINT', () => {
    closeDatabase();
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    closeDatabase();
    process.exit(0);
  });
}

start();
