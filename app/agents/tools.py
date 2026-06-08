"""
All Claude tool schemas.
These are the actions the HR chatbot can trigger.
"""

TOOLS = [
    {
        "name": "generate_jd",
        "description": (
            "Generate a complete job description for a role. "
            "Use this when HR wants to create a new job posting. "
            "Always show the generated JD to HR and ask for confirmation before posting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "stream": {
                    "type": "string",
                    "description": "Functional stream e.g. Developer, QA, AI/ML, UI/UX, HR",
                },
                "band": {
                    "type": "string",
                    "description": "Organizational band e.g. B7L, B7H, B6, B5",
                },
                "experience_min": {
                    "type": "integer",
                    "description": "Minimum years of experience required",
                },
                "skills_required": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "skill": {"type": "string"},
                            "priority": {"type": "string", "enum": ["required", "preferred"]},
                        },
                        "required": ["skill", "priority"],
                    },
                    "description": "List of required and preferred skills",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["standard", "priority", "critical"],
                    "description": "Hiring urgency level",
                },
                "employment_type": {
                    "type": "string",
                    "enum": ["full_time", "internship"],
                    "description": "Type of employment",
                },
                "ats_threshold": {
                    "type": "integer",
                    "description": "Minimum ATS score (0-100) to shortlist a candidate. Default 70.",
                },
                "role_expectations": {
                    "type": "string",
                    "description": "Optional additional context about the role",
                },
            },
            "required": ["stream", "band", "experience_min", "skills_required", "urgency", "employment_type"],
        },
    },
    {
        "name": "check_bench",
        "description": (
            "Check Webtrack for available internal employees on bench "
            "who match the given stream and band. "
            "Use this when HR wants to check internal availability before posting externally."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "stream": {"type": "string", "description": "Functional stream"},
                "band": {"type": "string", "description": "Organizational band"},
            },
            "required": ["stream", "band"],
        },
    },
    {
        "name": "post_job",
        "description": (
            "Publish a confirmed job posting to the careers page. "
            "Only call this after HR has explicitly confirmed the JD. "
            "Never post without confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_posting_id": {
                    "type": "string",
                    "description": "The TalentOS job posting ID to publish",
                },
            },
            "required": ["job_posting_id"],
        },
    },
    {
        "name": "get_job_status",
        "description": "Get the current status and pipeline summary of a job posting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_posting_id": {"type": "string"},
            },
            "required": ["job_posting_id"],
        },
    },
    {
        "name": "get_shortlisted_candidates",
        "description": "Get the list of shortlisted candidates for a job posting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_posting_id": {"type": "string"},
            },
            "required": ["job_posting_id"],
        },
    },
]
