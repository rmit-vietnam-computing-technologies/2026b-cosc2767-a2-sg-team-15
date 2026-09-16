#  RMIT University Vietnam
# Course: COSC2767|COSC2805 Systems Deployment and Operations
# Semester: 2026B
# Assessment: Assignment 2
# Author: Le Huy Phuong (Container image packaging)
# ID: s4130965
# Created  date: 8/09/2026
# Last modified: 13/09/2026
# Acknowledgement: Dockerfile was built through provided examples on RMIT Canvas modules
# Instructions on how to apply custom website's content into existing builder nodes were provided with Claude
# Instructions were followed and Dockerfile was written and modified by hand





# Build inside container
# Builder environment to build Vue frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package.json and packagelock.json to install related dependencies first
COPY package*.json ./
RUN npm install

# Copy existing source code in the current ec2-user host dirctory to /app in builder directory
COPY . .
RUN npm run build

# Use nginx to serve frontend
FROM nginx:alpine

# Copy built /dist into html of nginx
COPY --from=builder /app/dist/ /usr/share/nginx/html/


# Nginx
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