const { Pool } = require("pg");

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://postgres:root@localhost:5432/talentos",
});

// helper to generate dates
const d = (y, m, day) => new Date(y, m - 1, day);

// base seeds (you can extend manually too)
const baseUsers = [
  { emp_id: "EMP001", name: "Rahul Sharma", designation: "Software Engineer", department: "Engineering" },
  { emp_id: "EMP002", name: "Priya Patel", designation: "Senior Software Engineer", department: "Engineering" },
  { emp_id: "EMP003", name: "Amit Kumar", designation: "AI/ML Engineer", department: "Engineering" },
  { emp_id: "EMP004", name: "Sneha Reddy", designation: "QA Lead", department: "Quality Assurance" },
  { emp_id: "EMP005", name: "Vikram Singh", designation: "DevOps Engineer", department: "Infrastructure" },
  { emp_id: "EMP006", name: "Neha Joshi", designation: "Product Owner - Management Captain", department: "Product" },
  { emp_id: "EMP007", name: "Karan Mehta", designation: "Project Manager", department: "Management" },
  { emp_id: "EMP008", name: "Anjali Verma", designation: "Business Analyst", department: "Business" },
  { emp_id: "EMP009", name: "Rohit Gupta", designation: "Team Lead", department: "Engineering" },
  { emp_id: "EMP010", name: "Pooja Nair", designation: "UI/UX Lead", department: "Design" },

  { emp_id: "EMP011", name: "Arjun Iyer", designation: "Senior DevOps Engineer", department: "Infrastructure" },
  { emp_id: "EMP012", name: "Meera Shah", designation: "HR Manager", department: "HR" },
  { emp_id: "EMP013", name: "Siddharth Jain", designation: "Finance Manager", department: "Finance" },
  { emp_id: "EMP014", name: "Kavya Nair", designation: "Designer Intern", department: "Design" },
  { emp_id: "EMP015", name: "Manish Yadav", designation: "QA Intern", department: "Quality Assurance" },
  { emp_id: "EMP016", name: "Ritika Kapoor", designation: "Associate QA", department: "Quality Assurance" },
  { emp_id: "EMP017", name: "Aditya Roy", designation: "Principal Engineer", department: "Engineering" },
  { emp_id: "EMP018", name: "Divya Menon", designation: "Senior QA", department: "Quality Assurance" },
  { emp_id: "EMP019", name: "Nikhil Agarwal", designation: "Senior PM", department: "Management" },
  { emp_id: "EMP020", name: "Simran Kaur", designation: "Senior Designer", department: "Design" },

  { emp_id: "EMP021", name: "Harsh Vardhan", designation: "AI Team Lead", department: "Engineering" },
  { emp_id: "EMP022", name: "Ayesha Khan", designation: "HR Generalist I", department: "HR" },
  { emp_id: "EMP023", name: "Deepak Mishra", designation: "Delivery Manager", department: "Management" },
  { emp_id: "EMP024", name: "Tanvi Desai", designation: "Associate Designer", department: "Design" },
  { emp_id: "EMP025", name: "Gaurav Bansal", designation: "DevOps Team Lead", department: "Infrastructure" },
  { emp_id: "EMP026", name: "Shreya Bose", designation: "Finance Associate", department: "Finance" },
  { emp_id: "EMP027", name: "Ramesh Gupta", designation: "Managing Director", department: "Leadership" },
  { emp_id: "EMP028", name: "Alok Srivastava", designation: "CTO", department: "Leadership" },
  { emp_id: "EMP029", name: "Nisha Arora", designation: "COO", department: "Leadership" },
  { emp_id: "EMP030", name: "Vivek Shetty", designation: "CEO", department: "Leadership" },
];

// 🔥 generate remaining users (to reach 30)
function generateUsers(startIndex, count) {
  const users = [];
  for (let i = 0; i < count; i++) {
    const id = startIndex + i;
    users.push({
      emp_id: `EMP${String(id).padStart(3, "0")}`,
      email: `user${id}@talentos.com`,
      personal_email: `user${id}@gmail.com`,
      name: `User ${id}`,
      status: id % 2 === 0 ? "benched" : "allocated",
      user_type: "permanent",
      designation: "Software Engineer",
      department: "Engineering",
      phone_number: `+91-90000000${id}`,
      role: "Developer",
      work_mode: id % 2 === 0 ? "remote" : "hybrid",
      delivery_status: "available",
      work_location_type: "home",
      doj: d(2022, 1, (id % 28) + 1),
      doe: null,
      date_of_birth: d(1995, (id % 12) + 1, (id % 28) + 1),
      internship_duration: null,
      band: ["B1", "B2", "B3"][id % 3],
    });
  }
  return users;
}

const users = [
  ...baseUsers,
  ...generateUsers(3, 28), // total ~30
];

async function seed() {
  const client = await pool.connect();

  try {
    await client.query("BEGIN");

    // 🔥 Create table
// 💣 reset table (dev only)
await client.query(`DROP TABLE IF EXISTS users;`);

// 🔥 Create fresh table
await client.query(`
  CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    emp_id VARCHAR(20) UNIQUE,
    email TEXT,
    personal_email TEXT,
    name TEXT,
    status TEXT,
    user_type TEXT,
    designation TEXT,
    department TEXT,
    phone_number TEXT,
    role TEXT,
    work_mode TEXT,
    delivery_status TEXT,
    work_location_type TEXT,
    doj DATE,
    doe DATE,
    date_of_birth DATE,
    internship_duration INT,
    band TEXT,
    created_at TIMESTAMP DEFAULT NOW()
  );
`);

    // 🔥 Insert data
    const query = `
      INSERT INTO users (
        emp_id, email, personal_email, name, status, user_type,
        designation, department, phone_number, role, work_mode,
        delivery_status, work_location_type, doj, doe,
        date_of_birth, internship_duration, band
      )
      VALUES (
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18
      )
      ON CONFLICT (emp_id) DO NOTHING;
    `;

    for (const u of users) {
      await client.query(query, [
        u.emp_id,
        u.email,
        u.personal_email,
        u.name,
        u.status,
        u.user_type,
        u.designation,
        u.department,
        u.phone_number,
        u.role,
        u.work_mode,
        u.delivery_status,
        u.work_location_type,
        u.doj,
        u.doe,
        u.date_of_birth,
        u.internship_duration,
        u.band,
      ]);
    }

    await client.query("COMMIT");
    console.log("✅ Seeding completed");
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("❌ Error:", err);
  } finally {
    client.release();
    await pool.end();
  }
}

seed();