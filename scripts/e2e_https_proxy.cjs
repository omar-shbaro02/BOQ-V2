// Disposable loopback TLS edge for the production-build browser rehearsal.
const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");

const server = https.createServer({ key: fs.readFileSync(process.env.VAI_TEST_TLS_KEY), cert: fs.readFileSync(process.env.SSL_CERT_FILE) }, (request, response) => {
  const upstream = http.request({ hostname: "127.0.0.1", port: 3013, path: request.url, method: request.method, headers: request.headers }, (result) => {
    response.writeHead(result.statusCode, result.headers);
    result.pipe(response);
  });
  upstream.on("error", () => { response.writeHead(503); response.end("Test web server is starting"); });
  request.pipe(upstream);
});
server.listen(3012, "127.0.0.1");
