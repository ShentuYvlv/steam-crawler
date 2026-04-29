FROM node:20-slim

WORKDIR /app

COPY frontend/package*.json /app/
RUN npm install

COPY frontend /app

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
