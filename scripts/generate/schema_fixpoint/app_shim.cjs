// Runs the desktop app's schema.ts + migrations.ts (bundled by esbuild) on node:sqlite, without Electron.
// Usage: node app_shim.cjs <bundle.cjs> <base.db>
// The better-sqlite3 surface is the app's own (`app/scripts/quality/lib/node-sqlite-driver.cjs`, next
// to core like the migrations it runs). Logs of the migrations go to stderr; stdout gets one JSON
// line: {"calls": n, "ms": n, "error": null|string}.
const path = require('node:path')
const { Database } = require(path.resolve(__dirname, '..', '..', '..', '..', 'app', 'scripts', 'quality', 'lib', 'node-sqlite-driver.cjs'))

console.log = (...args) => console.error(...args)
console.warn = (...args) => console.error(...args)

const [bundlePath, dbPath] = process.argv.slice(2)

const { bootstrap } = require(path.resolve(bundlePath))
const db = new Database(dbPath)
db.pragma('journal_mode = WAL')
db.pragma('synchronous = NORMAL')
db.pragma('foreign_keys = ON')
db.pragma('busy_timeout = 5000')
const started = Date.now()
let error = null
try { bootstrap(db) } catch (e) { error = String((e && e.stack) || e) }
const calls = db.calls
db.close()
process.stdout.write(JSON.stringify({ calls, ms: Date.now() - started, error }) + '\n')
