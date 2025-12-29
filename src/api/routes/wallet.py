"""
Wallet API Routes
For caregiver operations (adding money, checking balance)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

from src.db.database import get_db
from src.db.models import User, LedgerEntry
from src.wallet.ledger import WalletLedger
from sqlalchemy import select

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


class TopUpRequest(BaseModel):
    """Request to add money to wallet"""
    phone_number: str = Field(..., description="User's phone number")
    amount: int = Field(..., gt=0, le=10000, description="Amount in rupees (max ₹10,000)")
    caregiver_phone: Optional[str] = Field(None, description="Caregiver's phone for verification")


class TopUpResponse(BaseModel):
    """Response for top-up operation"""
    success: bool
    transaction_id: str
    new_balance: int  # In rupees
    message: str


class BalanceResponse(BaseModel):
    """Response for balance inquiry"""
    current_balance: int  # In rupees
    locked_balance: int   # In rupees
    available_balance: int  # In rupees
    recent_transactions: list


@router.post("/topup", response_model=TopUpResponse)
async def add_money_to_wallet(
    request: TopUpRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Add money to user's prepaid wallet
    This is typically done by a caregiver before the senior uses Sahayak
    
    The senior never handles OTPs or UPI PINs during voice interaction.
    """
    # Normalize phone number
    phone = request.phone_number.replace(" ", "").replace("-", "")
    if not phone.startswith("+91"):
        phone = f"+91{phone[-10:]}"
    
    # Find user
    result = await db.execute(
        select(User).where(User.phone_number == phone)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User with phone {request.phone_number} not found"
        )
    
    # Verify caregiver if provided
    if request.caregiver_phone and user.caregiver_phone:
        caregiver_phone = request.caregiver_phone.replace(" ", "").replace("-", "")
        if not caregiver_phone.startswith("+91"):
            caregiver_phone = f"+91{caregiver_phone[-10:]}"
        
        if caregiver_phone != user.caregiver_phone:
            raise HTTPException(
                status_code=403,
                detail="Caregiver phone number doesn't match"
            )
    
    # Add money
    wallet = WalletLedger(db)
    amount_paise = request.amount * 100  # Convert to paise
    
    try:
        transaction_id = await wallet.add_credit(
            user_id=user.id,
            amount=amount_paise,
            source="CAREGIVER_TOPUP",
            description=f"Top-up of ₹{request.amount} by caregiver"
        )
        
        # Get new balance
        new_balance, _ = await wallet.get_balance(user.id)
        
        await db.commit()
        
        return TopUpResponse(
            success=True,
            transaction_id=transaction_id,
            new_balance=new_balance // 100,
            message=f"Successfully added ₹{request.amount} to {user.full_name}'s wallet"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance/{phone_number}", response_model=BalanceResponse)
async def get_wallet_balance(
    phone_number: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get wallet balance for a user
    """
    # Normalize phone number
    phone = phone_number.replace(" ", "").replace("-", "")
    if not phone.startswith("+91"):
        phone = f"+91{phone[-10:]}"
    
    # Find user
    result = await db.execute(
        select(User).where(User.phone_number == phone)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get recent transactions
    ledger_result = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user.id)
        .order_by(LedgerEntry.timestamp.desc())
        .limit(10)
    )
    transactions = ledger_result.scalars().all()
    
    return BalanceResponse(
        current_balance=user.current_balance // 100,
        locked_balance=user.locked_balance // 100,
        available_balance=(user.current_balance - user.locked_balance) // 100,
        recent_transactions=[
            {
                "id": str(t.id),
                "type": t.transaction_type.value,
                "amount": t.amount // 100,
                "description": t.description,
                "timestamp": t.timestamp.isoformat()
            }
            for t in transactions
        ]
    )


@router.get("/transactions/{phone_number}")
async def get_transaction_history(
    phone_number: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    Get transaction history for a user
    """
    phone = phone_number.replace(" ", "").replace("-", "")
    if not phone.startswith("+91"):
        phone = f"+91{phone[-10:]}"
    
    result = await db.execute(
        select(User).where(User.phone_number == phone)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get transactions
    ledger_result = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.user_id == user.id)
        .order_by(LedgerEntry.timestamp.desc())
        .limit(limit)
    )
    transactions = ledger_result.scalars().all()
    
    return {
        "user": user.full_name,
        "phone": phone_number,
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "type": t.transaction_type.value,
                "amount": f"₹{t.amount // 100}",
                "balance_after": f"₹{t.balance_after // 100}",
                "description": t.description,
                "timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            }
            for t in transactions
        ]
    }