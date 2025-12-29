"""
Tests for Wallet Ledger System
Phase 3: Prepaid Wallet System
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from src.wallet.ledger import (
    WalletLedger, 
    WalletRulesEngine,
    InsufficientBalanceError,
    TransactionLimitError,
    WalletError
)
from src.db.models import User, LedgerEntry, TransactionType


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = AsyncMock()
    session.begin_nested = MagicMock(return_value=AsyncMock())
    return session


@pytest.fixture
def mock_user():
    """Create a mock user"""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.internal_id = "user_test123"
    user.current_balance = 100000  # ₹1000 in paise
    user.locked_balance = 0
    return user


@pytest.fixture
def wallet_ledger(mock_db_session):
    return WalletLedger(mock_db_session)


@pytest.fixture
def rules_engine():
    return WalletRulesEngine()


class TestWalletLedger:
    
    @pytest.mark.asyncio
    async def test_get_balance(self, wallet_ledger, mock_db_session, mock_user):
        """Test getting wallet balance"""
        # Setup mock
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(
            current_balance=100000,
            locked_balance=10000
        )
        mock_db_session.execute.return_value = mock_result
        
        current, locked = await wallet_ledger.get_balance(mock_user.id)
        
        assert current == 100000
        assert locked == 10000
    
    @pytest.mark.asyncio
    async def test_check_and_lock_success(self, wallet_ledger, mock_db_session, mock_user):
        """Test successful fund locking"""
        # Setup mock for user query
        mock_user.current_balance = 100000
        mock_user.locked_balance = 0
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        
        order_id = uuid4()
        amount = 12000  # ₹120
        
        transaction_id = await wallet_ledger.check_and_lock(
            user_id=mock_user.id,
            amount=amount,
            reference_id=order_id,
            description="Test order"
        )
        
        assert transaction_id.startswith("txn_")
        assert mock_user.locked_balance == amount
    
    @pytest.mark.asyncio
    async def test_check_and_lock_insufficient_balance(self, wallet_ledger, mock_db_session, mock_user):
        """Test locking fails with insufficient balance"""
        mock_user.current_balance = 10000  # ₹100
        mock_user.locked_balance = 0
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(InsufficientBalanceError):
            await wallet_ledger.check_and_lock(
                user_id=mock_user.id,
                amount=50000,  # ₹500 - more than balance
                reference_id=uuid4()
            )
    
    @pytest.mark.asyncio
    async def test_check_and_lock_exceeds_limit(self, wallet_ledger, mock_db_session, mock_user):
        """Test locking fails when exceeding transaction limit"""
        mock_user.current_balance = 500000  # ₹5000
        
        with pytest.raises(TransactionLimitError):
            await wallet_ledger.check_and_lock(
                user_id=mock_user.id,
                amount=250000,  # ₹2500 - exceeds ₹2000 limit
                reference_id=uuid4()
            )
    
    @pytest.mark.asyncio
    async def test_confirm_debit(self, wallet_ledger, mock_db_session, mock_user):
        """Test confirming a locked amount as debit"""
        # Setup lock entry mock
        lock_entry = MagicMock(spec=LedgerEntry)
        lock_entry.amount = 12000
        lock_entry.reference_type = "ORDER"
        lock_entry.reference_id = uuid4()
        lock_entry.description = "Test order"
        
        mock_lock_result = MagicMock()
        mock_lock_result.scalar_one_or_none.return_value = lock_entry
        
        mock_user.current_balance = 100000
        mock_user.locked_balance = 12000
        
        mock_user_result = MagicMock()
        mock_user_result.scalar_one.return_value = mock_user
        
        mock_db_session.execute.side_effect = [mock_lock_result, mock_user_result]
        
        result = await wallet_ledger.confirm_debit(
            transaction_id="txn_test123",
            user_id=mock_user.id
        )
        
        assert result == True
        assert mock_user.current_balance == 100000 - 12000
        assert mock_user.locked_balance == 0
    
    @pytest.mark.asyncio
    async def test_auto_refund(self, wallet_ledger, mock_db_session, mock_user):
        """Test auto-refund when API fails"""
        # Setup lock entry mock
        lock_entry = MagicMock(spec=LedgerEntry)
        lock_entry.amount = 12000
        lock_entry.reference_type = "ORDER"
        lock_entry.reference_id = uuid4()
        lock_entry.description = "Test order"
        
        mock_lock_result = MagicMock()
        mock_lock_result.scalar_one_or_none.return_value = lock_entry
        
        mock_user.current_balance = 100000
        mock_user.locked_balance = 12000
        
        mock_user_result = MagicMock()
        mock_user_result.scalar_one.return_value = mock_user
        
        mock_db_session.execute.side_effect = [mock_lock_result, mock_user_result]
        
        result = await wallet_ledger.auto_refund(
            transaction_id="txn_test123",
            user_id=mock_user.id,
            reason="API failed"
        )
        
        assert result == True
        assert mock_user.locked_balance == 0  # Lock released
        assert mock_user.current_balance == 100000  # Balance unchanged


class TestWalletRulesEngine:
    
    def test_valid_transaction(self, rules_engine):
        """Test valid transaction passes all rules"""
        is_valid, error = rules_engine.validate_transaction(
            amount=12000,  # ₹120
            current_balance=100000,  # ₹1000
            locked_balance=0,
            daily_spent=0
        )
        
        assert is_valid == True
        assert error is None
    
    def test_exceeds_single_transaction_limit(self, rules_engine):
        """Test transaction exceeding single limit fails"""
        is_valid, error = rules_engine.validate_transaction(
            amount=250000,  # ₹2500
            current_balance=500000,
            locked_balance=0
        )
        
        assert is_valid == False
        assert "maximum" in error.lower()
    
    def test_insufficient_balance(self, rules_engine):
        """Test insufficient balance fails"""
        is_valid, error = rules_engine.validate_transaction(
            amount=50000,  # ₹500
            current_balance=30000,  # ₹300
            locked_balance=0
        )
        
        assert is_valid == False
        assert "insufficient" in error.lower()
    
    def test_balance_with_locked_amount(self, rules_engine):
        """Test available balance considers locked amount"""
        is_valid, error = rules_engine.validate_transaction(
            amount=50000,  # ₹500
            current_balance=100000,  # ₹1000
            locked_balance=60000  # ₹600 locked, only ₹400 available
        )
        
        assert is_valid == False
        assert "insufficient" in error.lower()
    
    def test_daily_limit_exceeded(self, rules_engine):
        """Test daily spending limit"""
        is_valid, error = rules_engine.validate_transaction(
            amount=100000,  # ₹1000
            current_balance=1000000,
            locked_balance=0,
            daily_spent=450000  # Already spent ₹4500 today
        )
        
        assert is_valid == False
        assert "daily" in error.lower()