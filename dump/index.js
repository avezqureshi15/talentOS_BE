const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

// DB config
const client = new Client({
  user: "postgres",
  password: "root",
  host: "localhost",
  port: 5432,
  database: "webtrak",
});

const TABLES = ["kpi_definitions", "designation", "bands"];

function toPythonFormat(obj) {
  return JSON.stringify(obj, null, 4)
    .replace(/true/g, "True")
    .replace(/false/g, "False")
    .replace(/null/g, "None");
}

async function dumpTable(tableName) {
  const res = await client.query(`SELECT * FROM ${tableName}`);

  const seeds = res.rows;

  const fileContent = `"""Seed data for the ${tableName} table."""

${tableName.toUpperCase()}_SEEDS = ${toPythonFormat(seeds)}
`;

  const filePath = path.join(__dirname, `${tableName}.seed.py`);

  fs.writeFileSync(filePath, fileContent);

  console.log(`✅ Dumped ${tableName} -> ${filePath}`);
}

async function main() {
  try {
    await client.connect();

    for (const table of TABLES) {
      await dumpTable(table);
    }

    await client.end();
    console.log("🔥 Done dumping all tables.");
  } catch (err) {
    console.error("❌ Error:", err);
    await client.end();
  }
}

main();