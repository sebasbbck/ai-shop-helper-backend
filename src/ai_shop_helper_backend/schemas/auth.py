from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class Token(SQLModel):
    """Schema for the access token response."""

    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(SQLModel):
    """Schema for verifying an email address."""

    token: str


class ResendVerificationRequest(SQLModel):
    """Schema for requesting a verification email resend."""

    email: EmailStr


class ForgotPasswordRequest(SQLModel):
    """Schema for requesting a password reset email."""

    email: EmailStr


class ResetPasswordRequest(SQLModel):
    """Schema for resetting a password using a token."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(SQLModel):
    """Schema for a generic message response."""

    message: str
