from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from ...database import get_db
from ..deps import get_current_user
from ...models.user import User
from ...models.letter import Letter
from ...models.separation import Separation
from ...schemas.letter import LetterCreate, LetterUpdate, LetterResponse
from ...services.ai_service import evaluate_love_letter

router = APIRouter(prefix="/letters", tags=["Letters"])

@router.post("/", response_model=LetterResponse)
async def create_letter(
    letter_data: LetterCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Ask Gemini to score how loving/forgiving the letter is (0-100)
    ai_score = await evaluate_love_letter(letter_data.content)

    new_letter = Letter(
        author_id=current_user.id,
        partner_id=current_user.partner_id,
        title=letter_data.title,
        content=letter_data.content,
        letter_type=letter_data.letter_type.lower() if letter_data.letter_type else None,
        ai_love_score=ai_score
    )
    db.add(new_letter)
    db.commit()
    db.refresh(new_letter)
    return new_letter

@router.get("/my", response_model=List[LetterResponse])
def get_my_letters(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Returns all letters the current user has written."""
    return db.query(Letter).filter(Letter.author_id == current_user.id).order_by(Letter.created_at.desc()).all()

@router.get("/partner/revealed", response_model=List[LetterResponse])
def get_revealed_partner_letters(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Returns letters written by the partner that have been revealed.
    MAGIC LOGIC: If an active separation has 3 or fewer days remaining, 
    all hidden 'love' letters from the partner will automatically be revealed!
    """
    if not current_user.partner_id:
        return []

    # 1. Check for an active separation
    sep = db.query(Separation).filter(
        (Separation.creator_id == current_user.id) | (Separation.partner_id == current_user.id),
        Separation.status == "active"
    ).first()

    if sep:
        days_remaining = (sep.expected_end_date - date.today()).days
        
        # 2. If 3 or fewer days remaining, reveal hidden letters with high AI Love Score (>= 80)
        if days_remaining <= 3:
            hidden_love_letters = db.query(Letter).filter(
                Letter.author_id == current_user.partner_id,
                Letter.ai_love_score >= 80,
                  Letter.is_revealed == False
            ).all()

            if hidden_love_letters:
                for letter in hidden_love_letters:
                    letter.is_revealed = True
                db.commit()
                # (Optional) Here we could trigger a notification service:
                # create_notification(db, current_user.id, "Love Letters Revealed!")

    # 3. Return all currently revealed letters from the partner
    revealed_letters = db.query(Letter).filter(
        Letter.author_id == current_user.partner_id,
        Letter.is_revealed == True
    ).order_by(Letter.created_at.desc()).all()

    return revealed_letters


@router.get("/{letter_id}", response_model=LetterResponse)
def get_letter(
    letter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns a single letter by ID. Only the author can access it."""
    letter = db.query(Letter).filter(
        Letter.id == letter_id,
        Letter.author_id == current_user.id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    return letter


@router.patch("/{letter_id}", response_model=LetterResponse)
async def update_letter(
    letter_id: int,
    update_data: LetterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Edit a letter's title and/or content.
    If content is changed, Gemini re-evaluates the AI love score.
    Only the author can edit their own letter.
    """
    letter = db.query(Letter).filter(
        Letter.id == letter_id,
        Letter.author_id == current_user.id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    if update_data.title is not None:
        letter.title = update_data.title

    if update_data.content is not None:
        letter.content = update_data.content
        # Re-score with Gemini since content changed
        letter.ai_love_score = await evaluate_love_letter(update_data.content)

    db.commit()
    db.refresh(letter)
    return letter


@router.delete("/{letter_id}")
def delete_letter(
    letter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Permanently deletes a letter. Only the author can delete their own letter."""
    letter = db.query(Letter).filter(
        Letter.id == letter_id,
        Letter.author_id == current_user.id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    db.delete(letter)
    db.commit()
    return {"success": True, "message": "Letter deleted successfully"}
