FROM nginx:1.27-alpine

RUN rm -f /etc/nginx/conf.d/default.conf

COPY api.conf /etc/nginx/conf.d/api.conf

EXPOSE 80 443

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
