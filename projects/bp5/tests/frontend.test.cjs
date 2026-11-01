// Keep every real frontend suite in the managed delivery check.
const fs = require('node:fs');
const path = require('node:path');
const suiteRoot = path.join(__dirname, '../web/tests');
for (const name of fs.readdirSync(suiteRoot).filter(n => n.endsWith('.test.cjs')).sort()) {
  require(path.join(suiteRoot, name));
}
