import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || '3001', 10),
  gitlab: {
    url: process.env.GITLAB_URL || 'https://gitlab.com',
    token: process.env.GITLAB_TOKEN || '',
    projectId: parseInt(process.env.GITLAB_PROJECT_ID || '4', 10),
  },
  db: {
    path: process.env.DB_PATH || './data/bsms.db',
  },
  cors: {
    origin: process.env.CORS_ORIGIN || 'http://localhost:5173',
  },
};
