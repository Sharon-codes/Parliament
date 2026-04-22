# Use a lightweight Node.js image to build
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Set the public URL for the build
ARG VITE_API_URL=https://sharon-codes-saathi-api.hf.space
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Use Nginx to serve the static files
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# For PWA support
COPY --from=build /app/dist/index.html /usr/share/nginx/html/404.html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
