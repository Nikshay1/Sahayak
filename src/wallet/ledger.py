"""
Prepaid Wallet System with Double-Entry Ledger
Phase 3: Financial Safety & Trust
"""

from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.db.models import User, LedgerEntry, TransactionType
from src.config.settings import settings
from src.config.constants import LogEventType
import logging

logger = logging.getLogger(__name__)


class WalletError(Exception):
    """Base wallet exception"""
    pass


class InsufficientBalanceError(WalletError):
    """Raised when balance is too low"""
    pass


class TransactionLimitError(WalletError):
    """Raised when transaction exceeds limits"""
    pass


class WalletLedger:
    """
    Double-Entry Ledger for Prepaid Wallet
    
    Key Principles:
    - Financial data is NEVER overwritten, only appended
    - Atomic check-and-deduct operations
    - Hard cap on transactions (₹2000)
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.max_transaction = settings.MAX_TRANSACTION_AMOUNT * 100  # Convert to paise
        
    async def get_balance(self, user_id: UUID) -> Tuple[int, int]:
        """
        Get current and locked balance
        
        Returns:
            Tuple of (available_balance, locked_balance) in paise
        """
        result = await self.db.execute(
            select(User.current_balance, User.locked_balance)
            .where(User.id == user_id)
        )
        row = result.first()
        
        if not row:
            raise WalletError(f"User {user_id} not found")
            
        return row.current_balance, row.locked_balance
    
    async def check_and_lock(
        self, 
        user_id: UUID, 
        amount: int,
        reference_id: UUID,
        description: str = "Order payment"
    ) -> str:
        """
        Phase 3, Task 3.2: Atomic Check-and-Deduct
        API execution cannot start unless funds are reserved
        
        Args:
            user_id: User UUID
            amount: Amount in paise
            reference_id: Order ID this lock is for
            description: Human-readable description
            
        Returns:
            transaction_id for this lock
            
        Raises:
            InsufficientBalanceError: If balance too low
            TransactionLimitError: If amount exceeds ₹2000
        """
        # Rule 1: Hard cap check
        if amount > self.max_transaction:
            raise TransactionLimitError(
                f"Transaction amount {amount/100} exceeds limit of ₹{settings.MAX_TRANSACTION_AMOUNT}"
            )
        
        transaction_id = f"txn_{uuid4().hex[:12]}"
        
        async with self.db.begin_nested():  # Savepoint for atomicity
            # Get current balance with row lock
            result = await self.db.execute(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise WalletError(f"User {user_id} not found")
            
            available = user.current_balance - user.locked_balance
            
            if available < amount:
                raise InsufficientBalanceError(
                    f"Available balance {available/100} is less than required {amount/100}"
                )
            
            # Create lock entry
            lock_entry = LedgerEntry(
                transaction_id=transaction_id,
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.LOCK,
                reference_type="ORDER",
                reference_id=reference_id,
                balance_after=user.current_balance,
                description=f"Lock for: {description}"
            )
            self.db.add(lock_entry)
            
            # Update locked balance
            user.locked_balance += amount
            
            await self.db.flush()
            
        logger.info(f"Locked {amount/100} for user {user_id}, txn: {transaction_id}")
        return transaction_id
    
    async def confirm_debit(
        self, 
        transaction_id: str,
        user_id: UUID
    ) -> bool:
        """
        Convert lock to actual debit after successful API execution
        
        Args:
            transaction_id: The lock transaction ID
            user_id: User UUID
            
        Returns:
            True if successful
        """
        async with self.db.begin_nested():
            # Find the lock entry
            result = await self.db.execute(
                select(LedgerEntry)
                .where(
                    LedgerEntry.transaction_id == transaction_id,
                    LedgerEntry.transaction_type == TransactionType.LOCK,
                    LedgerEntry.user_id == user_id
                )
            )
            lock_entry = result.scalar_one_or_none()
            
            if not lock_entry:
                raise WalletError(f"Lock transaction {transaction_id} not found")
            
            # Get user with lock
            user_result = await self.db.execute(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
            )
            user = user_result.scalar_one()
            
            amount = lock_entry.amount
            
            # Create debit entry
            debit_entry = LedgerEntry(
                transaction_id=transaction_id,
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.DEBIT,
                reference_type=lock_entry.reference_type,
                reference_id=lock_entry.reference_id,
                balance_after=user.current_balance - amount,
                description=f"Payment confirmed: {lock_entry.description}"
            )
            self.db.add(debit_entry)
            
            # Update balances
            user.current_balance -= amount
            user.locked_balance -= amount
            
            await self.db.flush()
            
        logger.info(f"Confirmed debit {amount/100} for user {user_id}, txn: {transaction_id}")
        return True
    
    async def auto_refund(
        self, 
        transaction_id: str,
        user_id: UUID,
        reason: str = "API execution failed"
    ) -> bool:
        """
        Phase 4, Task 4.3: Auto-refund when API fails after money is locked
        
        Args:
            transaction_id: The lock transaction ID
            user_id: User UUID
            reason: Reason for refund
            
        Returns:
            True if successful
        """
        async with self.db.begin_nested():
            # Find the lock entry
            result = await self.db.execute(
                select(LedgerEntry)
                .where(
                    LedgerEntry.transaction_id == transaction_id,
                    LedgerEntry.transaction_type == TransactionType.LOCK,
                    LedgerEntry.user_id == user_id
                )
            )
            lock_entry = result.scalar_one_or_none()
            
            if not lock_entry:
                raise WalletError(f"Lock transaction {transaction_id} not found")
            
            # Get user with lock
            user_result = await self.db.execute(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
            )
            user = user_result.scalar_one()
            
            amount = lock_entry.amount
            
            # Create unlock/refund entry
            refund_entry = LedgerEntry(
                transaction_id=transaction_id,
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.REFUND,
                reference_type=lock_entry.reference_type,
                reference_id=lock_entry.reference_id,
                balance_after=user.current_balance,  # Balance doesn't change, just unlock
                description=f"Auto-refund: {reason}"
            )
            self.db.add(refund_entry)
            
            # Release the lock
            user.locked_balance -= amount
            
            await self.db.flush()
            
        logger.info(f"Auto-refunded {amount/100} for user {user_id}, txn: {transaction_id}, reason: {reason}")
        return True
    
    async def add_credit(
        self,
        user_id: UUID,
        amount: int,
        source: str = "TOPUP",
        description: str = "Wallet top-up"
    ) -> str:
        """
        Add money to wallet (done by caregiver before call)
        
        Args:
            user_id: User UUID
            amount: Amount in paise
            source: Source of funds
            description: Human-readable description
            
        Returns:
            transaction_id
        """
        transaction_id = f"txn_{uuid4().hex[:12]}"
        
        async with self.db.begin_nested():
            user_result = await self.db.execute(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
            )
            user = user_result.scalar_one()
            
            new_balance = user.current_balance + amount
            
            credit_entry = LedgerEntry(
                transaction_id=transaction_id,
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.CREDIT,
                reference_type=source,
                balance_after=new_balance,
                description=description
            )
            self.db.add(credit_entry)
            
            user.current_balance = new_balance
            
            await self.db.flush()
            
        logger.info(f"Credited {amount/100} to user {user_id}, new balance: {new_balance/100}")
        return transaction_id


class WalletRulesEngine:
    """
    Phase 3, Task 3.2: Wallet Rules Engine
    Prevents accidental wallet drain
    """
    
    def __init__(self):
        self.max_single_transaction = settings.MAX_TRANSACTION_AMOUNT * 100
        self.daily_limit = 5000 * 100  # ₹5000 daily limit
        
    def validate_transaction(
        self, 
        amount: int, 
        current_balance: int,
        locked_balance: int,
        daily_spent: int = 0
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a transaction against all rules
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Rule 1: Hard cap on single transaction
        if amount > self.max_single_transaction:
            return False, f"Amount exceeds maximum of ₹{settings.MAX_TRANSACTION_AMOUNT}"
        
        # Rule 2: Sufficient balance
        available = current_balance - locked_balance
        if amount > available:
            return False, f"Insufficient balance. Available: ₹{available/100}"
        
        # Rule 3: Daily limit
        if daily_spent + amount > self.daily_limit:
            return False, f"Daily spending limit of ₹{self.daily_limit/100} would be exceeded"
        
        return True, None