const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

const client = new Client({
  connectionString: "postgresql://postgres:root@localhost:5432/talentos",
});

// ---- READ + PARSE PY FILE ----
function loadSeed(filePath, variableName) {
  let content = fs.readFileSync(filePath, "utf-8");

  // Extract array part
  const regex = new RegExp(`${variableName}\\s*=\\s*(\\[.*\\])`, "s");
  const match = content.match(regex);

  if (!match) {
    throw new Error(`❌ Could not find ${variableName} in ${filePath}`);
  }

  let data = match[1];

  // Convert Python → JS
  data = data
    .replace(/True/g, "true")
    .replace(/False/g, "false")
    .replace(/None/g, "null");

  return JSON.parse(data);
}

// ---- LOAD FILES ----
const BANDS_SEEDS = loadSeed(
  path.join(__dirname, "bands.seed.py"),
  "BANDS_SEEDS"
);

const DESIGNATION_SEEDS = loadSeed(
  path.join(__dirname, "designation.seed.py"),
  "DESIGNATION_SEEDS"
);

const KPI_DEFINITIONS_SEEDS = loadSeed(
  path.join(__dirname, "kpi_definitions.seed.py"),
  "KPI_DEFINITIONS_SEEDS"
);

// ---- CREATE TABLES ----
async function createTables() {
  await client.query(`
    CREATE TABLE IF NOT EXISTS bands (
        id INTEGER PRIMARY KEY,
        name VARCHAR(50) NOT NULL UNIQUE
    );
  `);

  await client.query(`
    CREATE TABLE IF NOT EXISTS designation (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        band_id INTEGER NOT NULL,
        department VARCHAR(100),
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY (band_id) REFERENCES bands(id)
    );
  `);

  await client.query(`
    CREATE TABLE IF NOT EXISTS kpi_definitions (
        id INTEGER PRIMARY KEY,
        band_id INTEGER NOT NULL,
        designation VARCHAR(100),
        department VARCHAR(100),
        kpi_name TEXT,
        weightage NUMERIC(5,2),
        active BOOLEAN,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY (band_id) REFERENCES bands(id)
    );
  `);

  console.log("✅ Tables created");
}

// ---- INSERT ----
async function insertData(table, data) {
  for (const row of data) {
    const keys = Object.keys(row);
    const values = Object.values(row);

    const cols = keys.join(", ");
    const placeholders = keys.map((_, i) => `$${i + 1}`).join(", ");

    await client.query(
      `INSERT INTO ${table} (${cols}) VALUES (${placeholders})
       ON CONFLICT (id) DO NOTHING`,
      values
    );
  }

  console.log(`✅ Inserted ${table}`);
}

// ---- MAIN ----
async function main() {
  try {
    await client.connect();

    await createTables();

    // ORDER MATTERS
    await insertData("bands", BANDS_SEEDS);
    await insertData("designation", DESIGNATION_SEEDS);
    await insertData("kpi_definitions", KPI_DEFINITIONS_SEEDS);

    console.log("🔥 Done");
  } catch (err) {
    console.error(err);
  } finally {
    await client.end();
  }
}

main();