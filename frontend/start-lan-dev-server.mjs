import { createServer } from 'vite';

const server = await createServer({
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
});

await server.listen();
server.printUrls();

async function shutdown() {
  await server.close();
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
