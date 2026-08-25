# DO NOT BUILD INSIDE CONTAINER, ONLY TAKE FROM EXISTING /dist
# Get a ngix docker image, version alpine
FROM nginx:alpine 

# Copy existing /dst created from npm run build
COPY dist /usr/share/nginx/html

# Copy runtime config of compiled Vue into current container
COPY public/config.js /usr/share/nginx/html/config.js

# Configure Ngix in order for Ngix to listen in on Port 80, configure the default webpage access of html folder. /dist already has a index.html file so It will find it there
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