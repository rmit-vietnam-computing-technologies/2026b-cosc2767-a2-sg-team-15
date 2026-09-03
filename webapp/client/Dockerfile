# DO NOT BUILD INSIDE CONTAINER, ONLY TAKE FROM EXISTING /dist
FROM nginx:alpine

# Copy existing /dst
COPY dist /usr/share/nginx/html

# Copy runtime config
COPY public/config.js /usr/share/nginx/html/config.js

# Configure Ngix
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location = /config.js { \
        add_header Cache-Control "no-store"; \
    } \
    location /assets/ { \
        add_header Cache-Control "public, max-age=31536000, immutable"; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]