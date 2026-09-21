# frontend/Dockerfile
FROM node:22-alpine AS base
WORKDIR /app

# Зависимости отдельно для кэширования слоёв
COPY package.json package-lock.json ./
RUN npm ci

# Копируем исходники
COPY . .

# Dev target: Vite dev server с HMR
FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Prod target: билд + nginx
FROM base AS build
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
