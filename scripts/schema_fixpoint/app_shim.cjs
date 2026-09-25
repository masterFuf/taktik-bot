// Runs the desktop app's schema.ts + migrations.ts (bundled by esbuild) on node:sqlite, without Electron.
// Usage: node app_shim.cjs <bundle.cjs> <base.db>
// A minimal better-sqlite3 surface (exec, prepare/run/get/all, pragma, transaction). Logs of the
// migrations go to stderr; stdout gets one JSON line: {"calls": n, "ms": n, "error": null|string}.
const path = require('node:path')
const { DatabaseSync } = require('node:sqlite')

console.log = (...args) => console.error(...args)
console.warn = (...args) => console.error(...args)

const [bundlePath, dbPath] = process.argv.slice(2)
let calls = 0

function norm(args) {
  return args.map(a => (typeof a === 'boolean' ? (a ? 1 : 0) : a))
}

class Statement {
  constructor(db, sql) { this.st = db._db.prepare(sql) }
  run(...a) { calls++; return this.st.run(...norm(a)) }
  get(...a) { calls++; return this.st.get(...norm(a)) }
  all(...a) { calls++; return this.st.all(...norm(a)) }
  iterate(...a) { calls++; return this.st.iterate(...norm(a)) }
}

class Database {
  constructor(p) { this._db = new DatabaseSync(p); this._tx = 0 }
  exec(sql) { calls++; this._db.exec(sql); return this }
  prepare(sql) { return new Statement(this, sql) }
  pragma(s, opts) {
    calls++
    const rows = this._db.prepare('PRAGMA ' + s).all()
    if (opts && opts.simple) { const r = rows[0]; return r ? Object.values(r)[0] : undefined }
    return rows
  }
  transaction(fn) {
    const self = this
    return (...args) => {
      const name = 'tx' + (++self._tx)
      self._db.exec('SAVEPOINT ' + name)
      try { const r = fn(...args); self._db.exec('RELEASE ' + name); return r }
      catch (e) { self._db.exec('ROLLBACK TO ' + name); self._db.exec('RELEASE ' + name); throw e }
    }
  }
  close() { this._db.close() }
}

const { bootstrap } = require(path.resolve(bundlePath))
const db = new Database(dbPath)
db.pragma('journal_mode = WAL')
db.pragma('synchronous = NORMAL')
db.pragma('foreign_keys = ON')
db.pragma('busy_timeout = 5000')
const started = Date.now()
let error = null
try { bootstrap(db) } catch (e) { error = String((e && e.stack) || e) }
db.close()
process.stdout.write(JSON.stringify({ calls, ms: Date.now() - started, error }) + '\n')
