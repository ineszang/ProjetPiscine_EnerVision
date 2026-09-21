# ==================
# Étape 1 : Build
# ==================

# Image pour frontend
FROM node:24-alpine3.22 AS builder

WORKDIR /app

COPY package.json package-lock.json* ./

# Installation des dépendances du projet avec npm
RUN  npm ci

# Copie du code source vers le conteneur
COPY . .

# Build 
RUN npm run build

# ==================
# Étape 2 : Runner
# ==================


FROM nginx:1.28.0-alpine3.21 AS runner

# Copie de la configuration de nginx
COPY --chown=root:root nginx.conf /etc/nginx/nginx.conf
RUN chmod 755 /etc/nginx/nginx.conf

# Copy the static build output from the build stage to Nginx's default HTML serving directory
COPY --chown=root:root --from=builder /app/dist/*/browser /usr/share/nginx/html
RUN chmod 755 /usr/share/nginx/html

# Create necessary directories with proper permissions for nginx
RUN mkdir -p /var/log/nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx /var/cache/nginx /usr/share/nginx/html

# Use a non-root user for security best practices
USER nginx

# Frontend : port 3000
EXPOSE 3000

# Start Nginx directly with custom config
ENTRYPOINT ["nginx", "-c", "/etc/nginx/nginx.conf"]
CMD ["-g", "daemon off;"]