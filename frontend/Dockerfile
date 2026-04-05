FROM node:20-alpine

WORKDIR /app

# Ensure we use cache for dependencies by copying package files first
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Expose Vite development port
EXPOSE 5173

# Setup entry point wrapper to rebuild OS-specific bindings mounted from host volume
CMD sh -c "npm rebuild esbuild rollup && npm run dev -- --host 0.0.0.0 --force"
