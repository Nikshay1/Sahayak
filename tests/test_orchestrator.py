"""
Tests for Execution Orchestrator
Phase 4: API Orchestration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.core.orchestrator import ExecutionOrchestrator, OrchestratorResult
from src.core.intent_engine import IntentSchema, IntentEngine
from src.wallet.ledger import WalletLedger, InsufficientBalanceError
from src.adapters.pharmacy_adapter import MockPharmacyAdapter
from src.services.notification_service import NotificationService
from src.schemas.logs import CallLogPacket
from src.config.constants import IntentType


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def mock_intent_engine():
    engine = MagicMock(spec=IntentEngine)
    engine.needs_clarification.return_value = False
    engine.should_refuse.return_value = False
    return engine


@pytest.fixture
def mock_wallet():
    wallet = AsyncMock(spec=WalletLedger)
    wallet.get_balance.return_value = (100000, 0)  # ₹1000 available
    wallet.check_and_lock.return_value = "txn_test123"
    wallet.confirm_debit.return_value = True
    return wallet


@pytest.fixture
def mock_pharmacy():
    pharmacy = AsyncMock(spec=MockPharmacyAdapter)
    pharmacy.check_availability.return_value = {
        "available": True,
        "price": 12000,
        "name": "Shelcal 500"
    }
    pharmacy.place_order.return_value = {
        "success": True,
        "order_id": "PH123456",
        "estimated_delivery": "5 PM"
    }
    return pharmacy


@pytest.fixture
def mock_notifications():
    return AsyncMock(spec=NotificationService)


@pytest.fixture
def orchestrator(mock_db_session, mock_intent_engine, mock_wallet, mock_pharmacy, mock_notifications):
    return ExecutionOrchestrator(
        db_session=mock_db_session,
        intent_engine=mock_intent_engine,
        wallet_ledger=mock_wallet,
        pharmacy_adapter=mock_pharmacy,
        notification_service=mock_notifications
    )


@pytest.fixture
def user_context():
    return {
        "internal_id": "user_test123",
        "medicine_history": [{"name": "Shelcal 500", "aliases": ["calcium"]}],
        "address": "Indiranagar",
        "full_address": "42, Gandhi Nagar, Indiranagar - 560038"
    }


@pytest.fixture
def call_log():
    return CallLogPacket(call_id="test_call_123", user_id="user_test123")


class TestOrchestrator:
    
    @pytest.mark.asyncio
    async def test_process_order_medicine_intent(
        self, orchestrator, mock_wallet, mock_pharmacy, user_context, call_log
    ):
        """Test processing a valid medicine order intent"""
        intent = IntentSchema(
            intent_type=IntentType.ORDER_MEDICINE,
            items=["Shelcal 500"],
            quantity=1,
            confidence_score=0.95,
            urgency="standard"
        )
        
        user_id = uuid4()
        
        # Mock medicine resolver
        with patch.object(orchestrator, 'medicine_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = [{
                "name": "Shelcal 500",
                "sku": "SHELCAL500",
                "matched": True,
                "typical_quantity": 1
            }]
            
            result = await orchestrator.process_intent(
                intent=intent,
                user_id=user_id,
                user_context=user_context,
                call_log=call_log
            )
        
        assert result.success == True
        assert result.requires_confirmation == True
        assert "Shelcal" in result.voice_response
        assert "120" in result.voice_response  # Price
    
    @pytest.mark.asyncio
    async def test_process_check_balance_intent(
        self, orchestrator, mock_wallet, user_context, call_log
    ):
        """Test processing a balance check intent"""
        intent = IntentSchema(
            intent_type=IntentType.CHECK_BALANCE,
            items=[],
            confidence_score=0.92,
            urgency="standard"
        )
        
        user_id = uuid4()
        
        result = await orchestrator.process_intent(
            intent=intent,
            user_id=user_id,
            user_context=user_context,
            call_log=call_log
        )
        
        assert result.success == True
        assert "1000" in result.voice_response  # Balance in rupees
        mock_wallet.get_balance.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_safe_refusal_for_unknown_intent(
        self, orchestrator, mock_intent_engine, user_context, call_log
    ):
        """Test safe refusal for unknown/unclear intent"""
        mock_intent_engine.should_refuse.return_value = True
        
        intent = IntentSchema(
            intent_type=IntentType.UNKNOWN,
            items=[],
            confidence_score=0.30,
            urgency="standard"
        )
        
        result = await orchestrator.process_intent(
            intent=intent,
            user_id=uuid4(),
            user_context=user_context,
            call_log=call_log
        )
        
        assert result.success == False
        assert "caregiver" in result.voice_response.lower()
    
    @pytest.mark.asyncio
    async def test_insufficient_balance_handling(
        self, orchestrator, mock_wallet, mock_pharmacy, user_context, call_log
    ):
        """Test handling of insufficient balance"""
        # Set low balance
        mock_wallet.get_balance.return_value = (5000, 0)  # Only ₹50
        
        intent = IntentSchema(
            intent_type=IntentType.ORDER_MEDICINE,
            items=["Shelcal 500"],
            quantity=1,
            confidence_score=0.95,
            urgency="standard"
        )
        
        with patch.object(orchestrator, 'medicine_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = [{
                "name": "Shelcal 500",
                "sku": "SHELCAL500",
                "matched": True
            }]
            
            result = await orchestrator.process_intent(
                intent=intent,
                user_id=uuid4(),
                user_context=user_context,
                call_log=call_log
            )
        
        assert result.success == False
        assert "not enough" in result.voice_response.lower() or "insufficient" in result.voice_response.lower()


class TestOrderExecution:
    
    @pytest.mark.asyncio
    async def test_execute_confirmed_order_success(
        self, orchestrator, mock_wallet, mock_pharmacy, mock_notifications, call_log
    ):
        """Test successful order execution after confirmation"""
        confirmation_context = {
            "type": "order_confirmation",
            "items": [{"name": "Shelcal 500", "sku": "SHELCAL500", "quantity": 1, "price": 12000}],
            "total_price": 12000,
            "user_id": str(uuid4()),
            "address": "42, Gandhi Nagar, Indiranagar - 560038"
        }
        
        # Mock the database operations
        with patch.object(orchestrator.db, 'add'), \
             patch.object(orchestrator.db, 'flush', new_callable=AsyncMock):
            
            result = await orchestrator.execute_confirmed_order(
                confirmation_context=confirmation_context,
                call_log=call_log
            )
        
        assert result.success == True
        assert result.order_id is not None
        assert "Done" in result.voice_response
        mock_wallet.check_and_lock.assert_called_once()
        mock_wallet.confirm_debit.assert_called_once()
        mock_pharmacy.place_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_order_api_failure_triggers_refund(
        self, orchestrator, mock_wallet, mock_pharmacy, call_log
    ):
        """Test that API failure triggers automatic refund"""
        # Make pharmacy API fail
        mock_pharmacy.place_order.return_value = {
            "success": False,
            "error": "Pharmacy system unavailable"
        }
        
        confirmation_context = {
            "type": "order_confirmation",
            "items": [{"name": "Shelcal 500", "sku": "SHELCAL500", "quantity": 1, "price": 12000}],
            "total_price": 12000,
            "user_id": str(uuid4()),
            "address": "Test Address"
        }
        
        with patch.object(orchestrator.db, 'add'), \
             patch.object(orchestrator.db, 'flush', new_callable=AsyncMock):
            
            result = await orchestrator.execute_confirmed_order(
                confirmation_context=confirmation_context,
                call_log=call_log
            )
        
        assert result.success == False
        assert "trouble" in result.voice_response.lower()
        mock_wallet.auto_refund.assert_called_once()