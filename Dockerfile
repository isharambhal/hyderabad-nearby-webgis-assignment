# Stage 1: Prepare website files
FROM alpine:3.21 AS build

WORKDIR /site
COPY client/ /site/

# Stage 2: Serve using Nginx
FROM nginx:alpine

COPY --from=build /site/ /usr/share/nginx/html/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
