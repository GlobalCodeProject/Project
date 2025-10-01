from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter()

class TestEmailBody(BaseModel):
    to: EmailStr | None = None
    subject: str = "Test email from SPO"
    body: str = "If you can read this, email works."

@router.post("/debug/email")
def send_test_email(body: TestEmailBody, request: Request):
    mailer = request.app.state.mailer  # injected in main.py
    try:
        mailer.send_plain(
            to_addr=body.to,       # if None, Mailer will fall back to settings.smtp_to
            subject=body.subject,
            text=body.body,
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"send error: {e}")
