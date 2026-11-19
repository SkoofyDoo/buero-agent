from dataclasses import dataclass, field
from typing import List


# Client Data
@dataclass
class Client:
    id: str = 0
    name: str = ""
    email: str = ""
    company: str = ""
    phone: str = ""
    folder_type: str = ""    # potencial | client
    status: str = ""         # potencial | active | inactive
    notes: str = ""

# Termine
@dataclass
class Appointment:
    id: int = 0
    date: str = ""
    time: str = ""
    participants: List[str] = field(default_factory=list)
    title: str = ""
    type: str = ""      # confirm | propose
    status: str = ""    # free | confllict

# Email Klasse
@dataclass
class EmailData:
    email_id: str = ""
    from_email: str = ""
    from_name: str = ""
    to: List[str] = field(default_factory=list)
    cc: List[str] = field(default_factory=list)
    subject: str = ""
    date: str = ""
    summary: str = ""
    type: str = ""
    language: str = ""
    attachments: List[str] = field(default_factory=list)
    appointments: List[Appointment] = field(default_factory=list)
    draft: str = ""
    client: Client = field(default_factory=Client)
    actions: List[str] = field(default_factory=list)
    priority: str = "normal"
    is_forwarded: bool = False
    is_reply: bool = False
    error: str = ""

  
@classmethod
def from_dict(cls, data: dict) -> "EmailData":
    appointments = []
    for appt in data.get("appointments", []):
        appointments.append(
            Appointment(
                id=appt.get("id", 0),
                date=appt.get("date", ""),
                time=appt.get("time", ""),
                participants=appt.get("participants", []),
                title=appt.get("title", ""),
                type=appt.get("type", ""),
                status=appt.get("status", ""),
            )
        )

    # Client — безопасно
    client_raw = data.get("client") or {}
    client = Client(
        id=client_raw.get("id", ""),
        name=client_raw.get("name", ""),
        email=client_raw.get("email", ""),
        company=client_raw.get("company", ""),
        phone=client_raw.get("phone", ""),
        folder_type=client_raw.get("folder_type", ""),
        status=client_raw.get("status", ""),
        notes=client_raw.get("notes", ""),
    )

    return cls(
        email_id=data.get("email_id", ""),
        from_email=data.get("from", ""),
        from_name=data.get("from_name", ""),
        to=data.get("to", []),
        cc=data.get("cc", []),
        subject=data.get("subject", ""),
        date=data.get("date", ""),
        summary=data.get("summary", ""),
        type=data.get("type", ""),
        language=data.get("language", ""),
        attachments=data.get("attachments", []),
        appointments=appointments,
        draft=data.get("draft", ""),
        client=client,
        actions=data.get("actions", []),
        priority=data.get("priority", "normal"),
        is_forwarded=data.get("is_forwarded", False),
        is_reply=data.get("is_reply", False),
        error=data.get("error", ""),
    )