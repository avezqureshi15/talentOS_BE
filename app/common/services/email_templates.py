from typing import Optional


def render_talentos_email(
    *,
    subject: str,
    preheader: str,
    recipient_name: str,
    body_html: str,
    cta_url: Optional[str] = None,
    cta_text: Optional[str] = None,
    footer_note: Optional[str] = None,
) -> str:
    """Render a fully inline-styled HTML email matching the TalentOS design language.

    Designed to mirror the frontend's dark-indigo aesthetic:
      - Near-black background (#0A0A0A)
      - Glass-like card with subtle border on #111111
      - Indigo accent (#6366F1) for CTAs and highlights
      - Aurora-inspired gradient header accent
      - Sora font stack, generous spacing
    """

    cta_block = ""
    if cta_url and cta_text:
        cta_block = f"""
        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="margin:28px 0 0;">
          <tr>
            <td align="center" style="border-radius:8px;background:linear-gradient(135deg,#6366F1,#4F46E5);padding:0;">
              <a href="{cta_url}" target="_blank"
                 style="display:inline-block;padding:14px 36px;font-family:'Sora',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;font-weight:600;line-height:1;color:#FFFFFF;text-decoration:none;border-radius:8px;letter-spacing:0.2px;">
                {cta_text}
              </a>
            </td>
          </tr>
        </table>"""

    footer = footer_note or "webHyre.ai — AI-powered recruitment intelligence."

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="x-apple-disable-message-reformatting">
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <title>{subject}</title>
  <!--[if mso]>
  <xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
  <![endif]-->
  <style>
    @media only screen and (max-width:600px) {{
      .tos-table {{ width:100% !important; }}
      .tos-card {{ padding:24px 20px !important; }}
      .tos-gutter {{ padding:16px 20px !important; }}
      .tos-code {{ font-size:13px !important; padding:14px !important; }}
      .tos-block {{ padding:16px !important; }}
      .tos-cta {{ padding:12px 24px !important; font-size:14px !important; }}
    }}
  </style>
  <!--[if mso]>
  <style type="text/css">
    .tos-card {{ background:#111111 !important; }}
    .tos-code {{ background:#1A1A1A !important; }}
    .tos-block {{ background:rgba(255,255,255,0.03) !important; }}
  </style>
  <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#0A0A0A;font-family:'Sora',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <!--[if mso]>
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0A0A0A;"><tr><td align="center">
  <![endif]-->

  <!-- Preheader (hidden) -->
  <div style="display:none;font-size:1px;color:#0A0A0A;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">
    {preheader}
  </div>

  <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%" style="background-color:#0A0A0A;">
    <tr>
      <td align="center" style="padding:40px 16px;">

        <!-- Outer card container -->
        <table class="tos-table" border="0" cellpadding="0" cellspacing="0" role="presentation" width="600" style="max-width:600px;width:100%;background-color:#111111;border-radius:12px;border:1px solid rgba(255,255,255,0.08);box-shadow:0 24px 80px rgba(0,0,0,0.6);">

          <!-- Aurora gradient accent line -->
          <tr>
            <td style="padding:0;border-radius:12px 12px 0 0;height:4px;font-size:0;line-height:0;background:linear-gradient(90deg,#6366F1,#A855F7,#EC4899,#06B6D4);">&zwnj;</td>
          </tr>

          <!-- Logo + header -->
          <tr>
            <td class="tos-gutter" style="padding:32px 36px 0;">
              <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">
                <tr>
                  <td style="font-size:22px;font-weight:800;letter-spacing:-0.02em;color:rgba(255,255,255,0.92);">
                    <span style="color:#6366F1;">✦</span>
                    <span style="color:#FFFFFF;">web</span>
                    <span style="color:#B0B5C0;">Hyre</span>
                    <span style="color:#B0B5C0;">.ai</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body content -->
          <tr>
            <td class="tos-gutter" style="padding:24px 36px;">

              <!-- Greeting -->
              <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">
                <tr>
                  <td style="font-size:15px;line-height:1.6;color:rgba(255,255,255,0.6);padding-bottom:8px;">
                    Hi {recipient_name},
                  </td>
                </tr>
              </table>

              <!-- Main body HTML -->
              {body_html}

              <!-- CTA -->
              {cta_block}

            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 36px;">
              <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">
                <tr>
                  <td style="height:1px;background:rgba(255,255,255,0.06);font-size:0;line-height:0;">&zwnj;</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td class="tos-gutter" style="padding:20px 36px 32px;">
              <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">
                <tr>
                  <td style="font-size:12px;line-height:1.5;color:rgba(255,255,255,0.35);">
                    {footer}
                    <br>
                    <span style="color:rgba(255,255,255,0.2);">© 2026 webHyre AI. All rights reserved.</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>

        <!-- Unsubscribe / preference -->
        <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="600" style="max-width:600px;width:100%;">
          <tr>
            <td align="center" style="padding:24px 16px 0;font-size:12px;color:rgba(255,255,255,0.25);">
              You are receiving this email because you are either part of Webknot
              Technologies or have applied to a position at Webknot Technologies.
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>

  <!--[if mso]>
  </td></tr></table>
  <![endif]-->
</body>
</html>"""


# ---- Reusable body blocks that callers compose into body_html ----

def block_text(text: str, bold: bool = False) -> str:
    """Simple paragraph block."""
    weight = "600" if bold else "400"
    return f"""
    <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%" style="margin-top:12px;">
      <tr>
        <td style="font-size:14px;line-height:1.7;color:rgba(255,255,255,0.6);font-weight:{weight};">
          {text}
        </td>
      </tr>
    </table>"""


def block_key_value(rows: list[tuple[str, str]]) -> str:
    """Structured info block — subtle dark surface with label:value pairs."""
    items = ""
    for label, value in rows:
        items += f"""
        <tr>
          <td style="padding:10px 18px;font-size:12px;color:rgba(255,255,255,0.4);white-space:nowrap;vertical-align:top;width:1%;">
            {label}
          </td>
          <td style="padding:10px 18px;font-size:14px;color:rgba(255,255,255,0.8);vertical-align:top;">
            {value}
          </td>
        </tr>"""

    return f"""
    <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%" style="margin-top:16px;background:rgba(255,255,255,0.03);border-radius:8px;border:1px solid rgba(255,255,255,0.06);">
      {items}
    </table>"""


def block_code(code: str, language: str = "") -> str:
    """Dark code-snippet block with monospace font."""
    escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lang_label = f"""<span style="font-size:11px;color:rgba(255,255,255,0.3);display:block;margin-bottom:8px;">{language}</span>""" if language else ""
    return f"""
    <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%" style="margin-top:16px;">
      <tr>
        <td style="background:#1A1A1A;border-radius:8px;border:1px solid rgba(255,255,255,0.06);padding:18px 20px;font-family:Consolas,Monaco,'Courier New',Courier,monospace;font-size:13px;line-height:1.6;color:#A1A1AA;">
          {lang_label}
          <code style="display:block;white-space:pre-wrap;word-break:break-word;">{escaped}</code>
        </td>
      </tr>
    </table>"""


def block_cta_line(text: str, url: str) -> str:
    """Inline text link styled as an accent."""
    return f"""
    <table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%" style="margin-top:16px;">
      <tr>
        <td style="font-size:14px;line-height:1.6;color:rgba(255,255,255,0.6);">
          <a href="{url}" target="_blank" style="color:#818CF8;text-decoration:underline;font-weight:500;">{text}</a>
        </td>
      </tr>
    </table>"""
