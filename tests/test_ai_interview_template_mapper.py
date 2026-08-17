from app.modules.hiring_requests.ai_interview_template_mapper import (
    build_interview_template_response,
)


def _meta():
    return {
        "candidate_name": "Ada Lovelace",
        "candidate_email": "ada@example.com",
        "role_title": "Backend Engineer",
        "applied_date": "2026-01-15T10:00:00Z",
    }


def _base_detail(**overrides):
    detail = {
        "id": "iid-1",
        "status": "assessed",
        "final_recommendation": "shortlisted",
        "summary": "Strong candidate.",
        "transcript_summary": "",
        "overall_score": 4.2,
        "technical_fit_score": 4.5,
        "communication_score": 3.8,
        "problem_solving_score": 4.0,
        "experience_score": 3.2,
        "role_alignment_score": 4.6,
        "strengths": ["Clear technical explanations", "Great problem solving approach"],
        "weaknesses": ["Limited experience with our stack"],
        "transcript": "Interviewer: Tell me about yourself.\nCandidate: I have five years of experience.",
        "interview_url": "https://poc.example/interview/tok",
    }
    detail.update(overrides)
    return detail


def test_verdict_mapping_shortlisted_advances():
    out = build_interview_template_response(_base_detail(), **_meta())
    assert out["aiRecommendation"] == "ADVANCE"


def test_verdict_mapping_rejected():
    out = build_interview_template_response(
        _base_detail(final_recommendation="rejected"), **_meta()
    )
    assert out["aiRecommendation"] == "REJECT"


def test_verdict_mapping_unknown_falls_back_to_potential_fit():
    out = build_interview_template_response(
        _base_detail(final_recommendation="mystery"), **_meta()
    )
    assert out["aiRecommendation"] == "POTENTIAL_FIT"


def test_topic_status_thresholds():
    out = build_interview_template_response(
        _base_detail(
            technical_fit_score=1.5,   # BELOW_BAR
            communication_score=3.0,   # MEETS_BAR
            problem_solving_score=4.5, # ABOVE_BAR
        ),
        **_meta(),
    )
    by_id = {t["id"]: t for t in out["topics"]}
    assert by_id["technical_fit"]["subCriteria"][0]["status"] == "BELOW_BAR"
    assert by_id["communication"]["subCriteria"][0]["status"] == "MEETS_BAR"
    assert by_id["problem_solving"]["subCriteria"][0]["status"] == "ABOVE_BAR"


def test_criteria_met_counts_dimensions_over_threshold():
    out = build_interview_template_response(
        _base_detail(
            technical_fit_score=4.0,
            communication_score=4.0,
            problem_solving_score=4.0,
            experience_score=2.0,
            role_alignment_score=2.0,
        ),
        **_meta(),
    )
    assert out["totalCriteria"] == 5
    assert out["criteriaMet"] == 3


def test_strengths_keyword_slotting_into_topics():
    detail = _base_detail(
        strengths=["Great communication skills", "Solid technical depth"],
        weaknesses=["Weak problem solving"],
    )
    out = build_interview_template_response(detail, **_meta())
    by_id = {t["id"]: t for t in out["topics"]}
    assert "Great communication skills" in by_id["communication"]["summaryBullets"]
    assert "Solid technical depth" in by_id["technical_fit"]["summaryBullets"]
    assert "Weak problem solving" in by_id["problem_solving"]["summaryBullets"]


def test_raw_transcript_parsed_into_speaker_utterances():
    out = build_interview_template_response(_base_detail(), **_meta())
    sections = out["transcriptSections"]
    assert len(sections) == 1
    utts = sections[0]["utterances"]
    assert utts[0]["speaker"] == "INTERVIEWER"
    assert utts[0]["text"] == "Tell me about yourself."
    assert utts[1]["speaker"] == "CANDIDATE"
    assert utts[1]["text"] == "I have five years of experience."


def test_structured_transcript_segments_preferred_over_raw():
    detail = _base_detail(
        transcript="ignored raw text",
        transcript_segments=[
            {"speaker": "interviewer", "text": "Hi", "timestamp": 5},
            {"speaker": "candidate", "text": "Hello", "timestamp": "00:10"},
        ],
    )
    out = build_interview_template_response(detail, **_meta())
    utts = out["transcriptSections"][0]["utterances"]
    assert utts[0]["speaker"] == "INTERVIEWER" and utts[0]["timeInSeconds"] == 5
    assert utts[1]["speaker"] == "CANDIDATE" and utts[1]["timeInSeconds"] == 10


def test_missing_transcript_gives_empty_sections_no_crash():
    detail = _base_detail(transcript="", transcript_segments=None)
    out = build_interview_template_response(detail, **_meta())
    assert out["transcriptSections"] == []
    assert out["transcript"] == []


def test_missing_summary_falls_back_to_transcript_summary():
    detail = _base_detail(summary=None, transcript_summary="Fallback summary")
    out = build_interview_template_response(detail, **_meta())
    assert out["aiSummary"] == "Fallback summary"


def test_five_scale_score_passes_through_unchanged():
    detail = _base_detail(overall_score=4.2)
    out = build_interview_template_response(detail, **_meta())
    assert out["overallScore"] == 4.2


def test_hundred_scale_score_is_normalized_to_five():
    detail = _base_detail(overall_score=84.0)
    out = build_interview_template_response(detail, **_meta())
    assert out["overallScore"] == 4.2


def test_hundred_scale_dimension_scores_normalize():
    detail = _base_detail(
        technical_fit_score=90.0,
        communication_score=75.0,
        problem_solving_score=40.0,
        experience_score=30.0,
        role_alignment_score=60.0,
    )
    out = build_interview_template_response(detail, **_meta())
    by_id = {t["id"]: t for t in out["topics"]}
    assert by_id["technical_fit"]["rating"] == 4.5
    assert by_id["communication"]["rating"] == 3.8
    assert by_id["problem_solving"]["rating"] == 2.0
    assert by_id["experience"]["rating"] == 1.5
    assert by_id["role_alignment"]["rating"] == 3.0


def test_poc_ai_user_prefix_transcript_parses_correctly():
    """POC's real transcript format uses `AI:` and `User:` prefixes."""
    detail = _base_detail(
        transcript=(
            "AI: Welcome to your technical interview. Let's begin.\n"
            "User: Sure, I'm ready.\n"
            "AI: Tell me about a project you led.\n"
            "User: I built a FastAPI service.\n"
        ),
        transcript_segments=None,
    )
    out = build_interview_template_response(detail, **_meta())
    utts = out["transcriptSections"][0]["utterances"]
    assert [u["speaker"] for u in utts] == ["AI", "CANDIDATE", "AI", "CANDIDATE"]
    assert utts[0]["text"] == "Welcome to your technical interview. Let's begin."
    assert utts[1]["text"] == "Sure, I'm ready."


def test_recording_url_propagates():
    out = build_interview_template_response(
        _base_detail(),
        recording_url="https://s3.example/presigned/abc.mp4",
        **_meta(),
    )
    assert out["recordingUrl"] == "https://s3.example/presigned/abc.mp4"


def test_recording_url_absent_is_none():
    out = build_interview_template_response(_base_detail(), **_meta())
    assert out["recordingUrl"] is None


def test_missing_candidate_meta_does_not_crash():
    out = build_interview_template_response(
        _base_detail(),
        candidate_name=None, candidate_email=None,
        role_title=None, applied_date=None,
    )
    assert out["candidateName"] == "Candidate"
    assert out["email"] == ""
    assert out["jobTitle"] == ""


def test_poc_rubric_verdicts_map():
    assert build_interview_template_response(
        _base_detail(final_recommendation="strong_hire"), **_meta()
    )["aiRecommendation"] == "ADVANCE"
    assert build_interview_template_response(
        _base_detail(final_recommendation="hire"), **_meta()
    )["aiRecommendation"] == "ADVANCE"
    assert build_interview_template_response(
        _base_detail(final_recommendation="hold"), **_meta()
    )["aiRecommendation"] == "POTENTIAL_FIT"
    assert build_interview_template_response(
        _base_detail(final_recommendation="no_hire"), **_meta()
    )["aiRecommendation"] == "REJECT"


def test_hr_decision_and_jd_fit_map():
    out = build_interview_template_response(
        _base_detail(hr_decision="shortlisted", jd_fit="Strong overlap on GCP skills."),
        **_meta(),
    )
    assert out["hrDecision"] == "shortlisted"
    assert out["jdFit"] == "Strong overlap on GCP skills."


def test_strengths_and_weaknesses_top_level():
    out = build_interview_template_response(_base_detail(), **_meta())
    assert out["strengths"] == [
        "Clear technical explanations",
        "Great problem solving approach",
    ]
    assert out["weaknesses"] == ["Limited experience with our stack"]


def test_transcript_summary_kept_separate_from_ai_summary():
    detail = _base_detail(
        summary="AI verdict summary.",
        transcript_summary="Raw conversation digest.",
    )
    out = build_interview_template_response(detail, **_meta())
    assert out["aiSummary"] == "AI verdict summary."
    assert out["transcriptSummary"] == "Raw conversation digest."


def test_timestamps_map_to_iso_strings():
    detail = _base_detail(
        created_at="2026-08-01T09:00:00Z",
        started_at="2026-08-01T09:05:00Z",
        completed_at="2026-08-01T09:45:00Z",
        expires_at="2026-08-08T09:00:00Z",
    )
    out = build_interview_template_response(detail, **_meta())
    assert out["createdAt"] == "2026-08-01T09:00:00Z"
    assert out["startedAt"] == "2026-08-01T09:05:00Z"
    assert out["completedAt"] == "2026-08-01T09:45:00Z"
    assert out["expiresAt"] == "2026-08-08T09:00:00Z"


def test_missing_timestamps_are_empty_strings():
    out = build_interview_template_response(_base_detail(), **_meta())
    assert out["createdAt"] == ""
    assert out["startedAt"] == ""
    assert out["completedAt"] == ""
    assert out["expiresAt"] == ""


def test_question_scores_and_rubric_total_map():
    detail = _base_detail(
        rubric_total=25,
        question_scores=[
            {
                "id": "q1",
                "question": "Explain GCP IAM.",
                "score": 8,
                "earned_score": 6,
                "notes": "Good but missed conditions.",
                "candidate_answer": "IAM policies...",
                "expected_points": ["Hierarchy", "Resource-based"],
                "candidate_points": ["Hierarchy"],
                "point_coverage": [
                    {"point": "Hierarchy", "covered": True},
                    {"point": "Resource-based", "covered": False},
                ],
            }
        ],
    )
    out = build_interview_template_response(detail, **_meta())
    assert out["rubricTotal"] == 25
    q = out["questionScores"][0]
    assert q["id"] == "q1"
    assert q["question"] == "Explain GCP IAM."
    assert q["score"] == 8
    assert q["earnedScore"] == 6
    assert q["notes"] == "Good but missed conditions."
    assert q["candidateAnswer"] == "IAM policies..."
    assert q["expectedPoints"] == ["Hierarchy", "Resource-based"]
    assert q["candidatePoints"] == ["Hierarchy"]
    assert q["pointCoverage"] == [
        {"point": "Hierarchy", "covered": True},
        {"point": "Resource-based", "covered": False},
    ]


def test_malformed_question_scores_do_not_crash():
    out = build_interview_template_response(
        _base_detail(question_scores=[None, "bad", {"question": "q"}]),
        **_meta(),
    )
    assert out["questionScores"] == [{
        "id": "",
        "question": "q",
        "score": None,
        "earnedScore": None,
        "notes": "",
        "candidateAnswer": "",
        "expectedPoints": [],
        "candidatePoints": [],
        "pointCoverage": None,
    }]
    assert out["rubricTotal"] is None


def test_ai_speaker_segments_map_to_ai():
    detail = _base_detail(
        transcript_segments=[
            {"speaker": "ai", "text": "Hello", "timestamp": 1},
            {"speaker": "assistant", "text": "Second AI turn", "timestamp": 2},
            {"speaker": "candidate", "text": "Hi", "timestamp": 3},
            {"speaker": "interviewer", "text": "Human interviewer", "timestamp": 4},
        ],
        transcript=None,
    )
    out = build_interview_template_response(detail, **_meta())
    speakers = [u["speaker"] for u in out["transcriptSections"][0]["utterances"]]
    assert speakers == ["AI", "AI", "CANDIDATE", "INTERVIEWER"]
