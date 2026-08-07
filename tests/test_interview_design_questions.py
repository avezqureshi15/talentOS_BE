from app.modules.interview_designs.interview_design_service import (
    _build_default_screening_sections,
    _clean_generated_questions,
    _clean_generated_sections,
)


def test_default_screening_seed_is_section_wise():
    sections = _build_default_screening_sections()
    assert len(sections) == 4
    assert [s["title"] for s in sections] == [
        "Availability & Notice Period",
        "Current Employment & Experience",
        "Compensation & Expectations",
        "Work Preferences & Interest",
    ]
    all_qs = [q for s in sections for q in s["questions"]]
    assert len(all_qs) == 8
    questions = [q["question"] for q in all_qs]
    assert "When are you available to start a new role? Are you currently looking actively?" in questions
    assert "What is your notice period at your current company?" in questions
    assert "Are you interested in moving forward with this opportunity?" in questions
    assert all(q["score"] == 5 for q in all_qs)
    assert all(q["timeAllocationMinutes"] == 0.25 for q in all_qs)
    assert sum(q["timeAllocationMinutes"] for q in all_qs) == 2.0
    assert all(q["expected_points"] == [] for q in all_qs)
    assert len({s["id"] for s in sections}) == 4
    assert len({q["id"] for q in all_qs}) == 8


def test_default_screening_seed_returns_independent_copies():
    first = _build_default_screening_sections()
    second = _build_default_screening_sections()
    assert first == second
    first[0]["title"] = "Mutated"
    assert second[0]["title"] == "Availability & Notice Period"


def test_review_questions_keep_score_and_expected_points():
    raw = [
        {"question": "How well does the candidate write idiomatic Go?", "score": 9,
         "expected_points": ["Correct concurrency patterns", "Clear error handling"]},
        {"question": "How clearly does the candidate communicate?", "score": 7,
         "expected_points": []},
        {"question": "  ", "score": 9, "expected_points": []},
    ]
    cleaned = _clean_generated_questions(raw, "review")
    assert len(cleaned) == 2
    assert cleaned[0]["score"] == 9
    assert cleaned[0]["expected_points"] == ["Correct concurrency patterns", "Clear error handling"]
    assert cleaned[1]["score"] == 7
    assert "expected_points" not in cleaned[1]
    assert all(q["id"] for q in cleaned)


def test_review_question_score_is_clamped():
    cleaned = _clean_generated_questions(
        [{"question": "Question?", "score": 42}], "review"
    )
    assert cleaned[0]["score"] == 10
    cleaned = _clean_generated_questions(
        [{"question": "Question?", "score": -3}], "review"
    )
    assert cleaned[0]["score"] == 1


def test_screening_questions_use_default_score():
    cleaned = _clean_generated_questions(
        [{"question": "When can you start?", "score": 9}], "screening"
    )
    assert cleaned[0]["score"] == 5
    assert "expected_points" not in cleaned[0]


def test_interview_questions_use_ai_timing():
    cleaned = _clean_generated_questions(
        [
            {"question": "Explain Go concurrency primitives.", "score": 9,
             "expected_points": [], "timeAllocationMinutes": 12},
            {"question": "Design a chat system.", "score": 8,
             "expected_points": [], "timeAllocationMinutes": 99},
            {"question": "Walk me through your projects.", "score": 6,
             "expected_points": [], "timeAllocationMinutes": 0},
            {"question": "Describe your debugging process.", "score": 5,
             "expected_points": []},
        ],
        "interview",
    )
    assert cleaned[0]["timeAllocationMinutes"] == 12
    assert cleaned[1]["timeAllocationMinutes"] == 60
    assert cleaned[2]["timeAllocationMinutes"] == 1
    assert cleaned[3]["timeAllocationMinutes"] == 5


def test_review_questions_have_no_timing():
    cleaned = _clean_generated_questions(
        [{"question": "Rate the candidate's communication.", "score": 8,
          "expected_points": []}],
        "review",
    )
    assert cleaned[0]["timeAllocationMinutes"] == 0


def test_clean_generated_sections_keeps_valid_structure():
    raw = [
        {
            "title": "Technical Competence",
            "type": "Q&A",
            "depth": "Deep Dive",
            "description": "Assesses hands-on engineering depth.",
            "questions": [
                {"question": "How do you design high-performance services?", "score": 9,
                 "expected_points": ["Tradeoff awareness", "Scalability thinking"]},
                {"question": "How do you debug a production outage?", "score": 8,
                 "expected_points": ["Root-cause analysis", "Systematic approach"]},
            ],
        },
        {
            "title": "Communication",
            "type": "CUSTOM",
            "depth": "Medium",
            "questions": [
                {"question": "How do you explain tradeoffs to stakeholders?", "score": 6,
                 "expected_points": []},
            ],
        },
    ]
    sections = _clean_generated_sections(raw)
    assert len(sections) == 2
    first = sections[0]
    assert first["title"] == "Technical Competence"
    assert first["type"] == "Q&A"
    assert first["depth"] == "Deep Dive"
    assert first["description"] == "Assesses hands-on engineering depth."
    assert len(first["questions"]) == 2
    assert first["questions"][0]["score"] == 9
    assert first["questions"][0]["expected_points"] == [
        "Tradeoff awareness",
        "Scalability thinking",
    ]
    assert all(q["timeAllocationMinutes"] == 0 for q in first["questions"])
    assert all(s["id"] for s in sections)
    assert all(q["id"] for s in sections for q in s["questions"])

    second = sections[1]
    assert second["type"] == "CUSTOM"
    assert second["depth"] == "Standard"
    assert second["description"] == ""


def test_clean_generated_sections_clamps_types_and_depths():
    raw = [
        {
            "title": "System Design",
            "type": "BOGUS",
            "depth": "Expert",
            "questions": [{"question": "Design a rate limiter.", "score": 8,
                           "expected_points": []}],
        },
    ]
    sections = _clean_generated_sections(raw)
    assert sections[0]["type"] == "Q&A"
    assert sections[0]["depth"] == "Standard"


def test_clean_generated_sections_drops_empty_sections():
    raw = [
        {"title": "No Questions", "type": "Q&A", "questions": []},
        {"title": "", "type": "Q&A", "questions": [
            {"question": "Q?", "score": 5, "expected_points": []}]},
        {"type": "Q&A", "questions": [
            {"question": "Q2?", "score": 5, "expected_points": []}]},
        {
            "title": "Valid",
            "type": "Q&A",
            "questions": [
                {"question": "Q3?", "score": 5, "expected_points": []},
                {"question": "", "score": 5, "expected_points": []},
            ],
        },
    ]
    sections = _clean_generated_sections(raw)
    assert len(sections) == 1
    assert sections[0]["title"] == "Valid"
    assert len(sections[0]["questions"]) == 1
