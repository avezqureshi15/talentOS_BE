# talentOS Database Schema

**16 tables** across **11 modules**, managed via SQLAlchemy + Alembic on PostgreSQL (Supabase).

---

## 1. todos

| Column | Type | Nullable | Default | PK | Notes |
|--------|------|----------|---------|----|-------|
| id | Integer | NO | autoincrement | YES | |
| title | String(255) | NO | | | |
| description | Text | YES | | | |
| is_completed | Boolean | NO | `false` | | |
| created_at | Timestamptz | NO | `now()` | | |

---

## 2. users

| Column | Type | Nullable | Default | PK | Unique | Notes |
|--------|------|----------|---------|----|--------|-------|
| id | Integer | NO | autoincrement | YES | | |
| emp_id | String(50) | NO | | | YES | |
| email | String(255) | NO | | | YES | |
| personal_email | String(255) | YES | | | | |
| name | String(255) | NO | | | | |
| status | String(50) | NO | | | | |
| user_type | String(50) | NO | | | | |
| designation | String(255) | NO | | | | |
| department | String(255) | NO | | | | |
| phone_number | String(20) | YES | | | | |
| role | String(100) | NO | | | | |
| work_mode | String(50) | NO | | | | |
| delivery_status | String(50) | NO | | | | |
| work_location_type | String(50) | NO | | | | |
| doj | Date | NO | | | | |
| doe | Date | YES | | | | |
| date_of_birth | Date | NO | | | | |
| internship_duration | Integer | YES | | | | |
| band | String(50) | NO | | | | |
| skills | Text | YES | | | | |
| created_at | Timestamptz | NO | `now()` | | | |

---

## 3. bands

| Column | Type | Nullable | Default | PK |
|--------|------|----------|---------|----|
| id | Integer | NO | autoincrement | YES |
| name | String(255) | NO | | |

## 4. designation

| Column | Type | Nullable | Default | PK | FK |
|--------|------|----------|---------|----|----|
| id | Integer | NO | autoincrement | YES | |
| name | String(255) | NO | | | |
| band_id | Integer | NO | | | `bands.id` |
| department | String(255) | NO | | | |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

## 5. kpi_definitions

| Column | Type | Nullable | Default | PK | FK |
|--------|------|----------|---------|----|----|
| id | Integer | NO | autoincrement | YES | |
| band_id | Integer | NO | | | `bands.id` |
| designation | String(255) | NO | | | |
| department | String(255) | NO | | | |
| kpi_name | String(255) | NO | | | |
| weightage | Integer | NO | | | |
| active | Boolean | NO | `true` | | |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

---

## 6. hiring_requests

| Column | Type | Nullable | Default | PK | Unique | Notes |
|--------|------|----------|---------|----|--------|-------|
| id | UUID | NO | `uuid4` | YES | | |
| title | String(255) | NO | | | | |
| department | String(255) | NO | | | | |
| location | String(255) | NO | | | | |
| type | String(100) | NO | | | | |
| description | Text | NO | | | | |
| requirements | JSON | YES | | | | |
| benefits | JSON | YES | | | | |
| is_active | Boolean | NO | `false` | | | |
| custom_evaluation_criteria | Text | YES | | | | |
| supabase_job_id | UUID | YES | | | YES | |
| deleted_at | Timestamptz | YES | | | | Soft delete |
| created_at | Timestamptz | NO | `now()` | | | |
| updated_at | Timestamptz | NO | `now()` | | | |

---

## 7. candidates

| Column | Type | Nullable | Default | PK | Unique | Index |
|--------|------|----------|---------|----|--------|-------|
| id | Integer | NO | autoincrement | YES | | |
| application_id | String(255) | NO | | | YES | YES |
| job_id | String(255) | NO | | | | YES |
| candidate_name | String(255) | YES | | | | |
| candidate_email | String(255) | YES | | | | |
| candidate_phone | String(30) | YES | | | | |
| cover_letter | Text | YES | | | | |
| resume_url | String(1024) | YES | | | | |
| current_ctc | String(50) | YES | | | | |
| expected_ctc | String(50) | YES | | | | |
| location | String(255) | YES | | | | |
| years_of_experience | String(10) | YES | | | | |
| notice_period | String(50) | YES | | | | |
| how_did_you_hear | String(100) | YES | | | | |
| linkedin_url | String(1024) | YES | | | | |
| scheduled | Boolean | NO | `false` | | | |
| status | String(30) | NO | `QUEUED` | | | YES |
| fit_score | Integer | YES | | | | |
| summary_md | Text | YES | | | | |
| ats_threshold_used | Integer | YES | | | | |
| attempts | Integer | NO | `0` | | | |
| error_reason | Text | YES | | | | |
| created_at | Timestamptz | NO | `now()` | | | |
| updated_at | Timestamptz | NO | `now()` | | | |
| evaluated_at | Timestamptz | YES | | | | |

Status enum: `QUEUED`, `PROCESSING`, `SHORTLISTED`, `REJECTED`, `INVALID`, `FAILED`

---

## 8. slots

| Column | Type | Nullable | Default | PK | Index |
|--------|------|----------|---------|----|-------|
| id | UUID | NO | `uuid4` | YES | |
| emp_id | String(50) | NO | | | YES |
| start_at | Timestamptz | NO | | | |
| end_at | Timestamptz | NO | | | |
| status | String(20) | NO | `available` | | |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

Status enum: `available`, `booked`, `inactive`
Constraint: `end_at > start_at`

---

## 9. alerts

| Column | Type | Nullable | Default | PK | Index |
|--------|------|----------|---------|----|-------|
| id | UUID | NO | `uuid4` | YES | |
| emp_id | String(50) | NO | | | YES |
| type | String(10) | NO | `SLOTS` | | |
| is_read | Boolean | NO | `false` | | YES |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

Type enum: `SLOTS`, `REVIEW`

---

## 10. forms

| Column | Type | Nullable | Default | PK | Index |
|--------|------|----------|---------|----|-------|
| id | UUID | NO | `uuid4` | YES | |
| emp_id | String(50) | NO | | | YES |
| type | String(10) | NO | `SLOTS` | | |
| status | String(10) | NO | `SENT` | | |
| last_sent_at | Timestamptz | NO | | | |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

Type enum: `SLOTS`, `REVIEW`
Status enum: `SENT`, `SUBMITTED`, `EXPIRED`

---

## 11. refresh_tokens

| Column | Type | Nullable | Default | PK | Unique | Index |
|--------|------|----------|---------|----|--------|-------|
| id | Integer | NO | autoincrement | YES | | |
| token_hash | String(255) | NO | | | YES | YES |
| user_id | Integer | NO | | | | |
| expires_at | Timestamptz | NO | | | | |
| created_at | Timestamptz | NO | `now()` | | | |

---

## 12. chats

| Column | Type | Nullable | Default | PK | FK | Index |
|--------|------|----------|---------|----|----|-------|
| id | UUID | NO | `uuid4` | YES | | |
| user_id | Integer | NO | | | `users.id` | YES |
| title | String(500) | NO | | | | |
| created_at | Timestamptz | NO | `now()` | | | |
| updated_at | Timestamptz | NO | `now()` | | | |

## 13. messages

| Column | Type | Nullable | Default | PK | Index |
|--------|------|----------|---------|----|-------|
| id | Integer | NO | autoincrement | YES | |
| chat_id | UUID | NO | | | YES |
| role | String(50) | NO | | | |
| content | Text | NO | | | |
| created_at | Timestamptz | NO | `now()` | | |

---

## 14. rounds

| Column | Type | Nullable | Default | PK | FK |
|--------|------|----------|---------|----|----|
| id | UUID | NO | `uuid4` | YES | |
| candidate_id | Integer | NO | | | `candidates.id` |
| slot_id | UUID | NO | | | `slots.id` |
| jd_id | UUID | NO | | | `hiring_requests.id` |
| ai_verdict | Text | YES | | | |
| hr_verdict | Text | YES | | | |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

## 15. round_interviewers

| Column | Type | Nullable | Default | PK | FK |
|--------|------|----------|---------|----|----|
| id | UUID | NO | `uuid4` | YES | |
| round_id | UUID | NO | | | `rounds.id` |
| employee_id | Integer | NO | | | `users.id` |
| verdict | Text | YES | | | |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

## 16. reviews

| Column | Type | Nullable | Default | PK | FK |
|--------|------|----------|---------|----|----|
| id | UUID | NO | `uuid4` | YES | |
| round_id | UUID | NO | | | `rounds.id` |
| employee_id | Integer | NO | | | `users.id` |
| summary | Text | YES | | | |
| status | String(50) | NO | | | |
| created_at | Timestamptz | NO | `now()` | | |
| updated_at | Timestamptz | NO | `now()` | | |

---

## Foreign Key Relationships

```
bands.id                     <──  designation.band_id
bands.id                     <──  kpi_definitions.band_id

users.id                     <──  chats.user_id
users.id                     <──  round_interviewers.employee_id
users.id                     <──  reviews.employee_id

candidates.id                <──  rounds.candidate_id
slots.id                     <──  rounds.slot_id
hiring_requests.id           <──  rounds.jd_id

rounds.id                    <──  round_interviewers.round_id
rounds.id                    <──  reviews.round_id
```

---

## Tables by Module

| Module | Tables |
|--------|--------|
| todo | `todos` |
| users | `users` |
| designation | `bands`, `designation`, `kpi_definitions` |
| hiring_requests | `hiring_requests` |
| evaluations | `candidates` |
| slots | `slots` |
| alerts | `alerts` |
| forms | `forms` |
| auth | `refresh_tokens` |
| chat | `chats`, `messages` |
| interviews | `rounds`, `round_interviewers`, `reviews` |
