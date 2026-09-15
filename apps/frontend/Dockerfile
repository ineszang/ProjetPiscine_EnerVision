# Image pour frontend
FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json* ./

# Installation des dépendances du projet avec npm
RUN --mount=type=cache,target=/root/.npm npm ci

# Copie du code source vers le conteneur
COPY . .

# Build 
RUN npm run build