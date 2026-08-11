from app.modules.email.email_template_registry import (
    all_template_specs,
    format_template,
    get_template_spec,
    tokenize,
)
from app.modules.email.email_template_service import html_to_text


def test_registry_has_all_templates():
    keys = [spec.key for spec in all_template_specs()]
    assert keys == [
        "slot_form",
        "slot_form_reminder",
        "review_form",
        "review_form_reminder",
        "interview_invite",
        "interview_slot",
        "invite",
    ]


def test_defaults_are_tokenized_and_renderable():
    for spec in all_template_specs():
        assert spec.default_subject
        assert spec.default_html
        # Seeded defaults must keep placeholders so edits + rendering work.
        # The recipient greeting and CTA are injected by the branded shell, so
        # their tokens live in the shell, not in the editable message body.
        body_tokens = set(spec.placeholders)
        if spec.recipient_placeholder:
            body_tokens.discard(spec.recipient_placeholder)
        if spec.cta_url_placeholder:
            body_tokens.discard(spec.cta_url_placeholder)
        for key in body_tokens:
            assert tokenize(key) in spec.default_html


def test_render_with_real_context_removes_tokens():
    for spec in all_template_specs():
        subject, _plain, html = spec.default_render(spec.sample_context)
        assert "{{" not in html
        assert "}}" not in html
        assert subject == format_template(spec.default_subject, spec.sample_context)


def test_html_to_text_strips_markup():
    text = html_to_text("<p>Hi <strong>Alex</strong>,</p><a href=\"https://x.test\">link</a>")
    assert "Alex" in text
    assert "https://x.test" in text
    assert "<" not in text


def test_get_template_spec_missing():
    assert get_template_spec("does_not_exist") is None
