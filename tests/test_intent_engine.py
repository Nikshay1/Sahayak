"""
Tests for Intent Parsing Engine
"""

import pytest
from unittest.mock import AsyncMock, patch
from src.core.intent_engine import IntentEngine, IntentSchema
from src.config.constants import IntentType


@pytest.fixture
def intent_engine():
    return IntentEngine()


@pytest.fixture
def user_context():
    return {
        "internal_id": "user_abc123",
        "medicine_history": [
            {"name": "Shelcal 500", "aliases": ["calcium", "calcium tablet"]},
            {"name": "Atorvastatin 10mg", "aliases": ["heart medicine"]}
        ]
    }


class TestIntentEngine:
    
    @pytest.mark.asyncio
    async def test_parse_order_medicine_intent(self, intent_engine, user_context):
        """Test parsing a clear medicine order request"""
        with patch.object(intent_engine, 'client') as mock_client:
            mock_response = AsyncMock()
            mock_response.choices = [
                AsyncMock(message=AsyncMock(content='{"intent_type": "ORDER_MEDICINE", "items": ["Shelcal 500"], "quantity": 1, "confidence_score": 0.95, "urgency": "standard", "clarification_needed": null, "raw_entities": {}}'))
            ]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            intent = await intent_engine.parse_intent(
                "Mujhe calcium ki dawai chahiye",
                user_context
            )
            
            assert intent.intent_type == IntentType.ORDER_MEDICINE
            assert intent.confidence_score >= 0.85
            assert len(intent.items) > 0
    
    @pytest.mark.asyncio
    async def test_parse_check_balance_intent(self, intent_engine, user_context):
        """Test parsing a balance check request"""
        with patch.object(intent_engine, 'client') as mock_client:
            mock_response = AsyncMock()
            mock_response.choices = [
                AsyncMock(message=AsyncMock(content='{"intent_type": "CHECK_BALANCE", "items": [], "quantity": null, "confidence_score": 0.92, "urgency": "standard", "clarification_needed": null, "raw_entities": {}}'))
            ]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            intent = await intent_engine.parse_intent(
                "Kitne paise hain mere wallet mein",
                user_context
            )
            
            assert intent.intent_type == IntentType.CHECK_BALANCE
            assert intent.confidence_score >= 0.85
    
    @pytest.mark.asyncio
    async def test_unclear_request_needs_clarification(self, intent_engine, user_context):
        """Test that unclear requests get low confidence"""
        with patch.object(intent_engine, 'client') as mock_client:
            mock_response = AsyncMock()
            mock_response.choices = [
                AsyncMock(message=AsyncMock(content='{"intent_type": "ORDER_MEDICINE", "items": [], "quantity": null, "confidence_score": 0.45, "urgency": "standard", "clarification_needed": "medicine_name", "raw_entities": {}}'))
            ]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            intent = await intent_engine.parse_intent(
                "Woh dawai chahiye... woh jo main leti hoon",
                user_context
            )
            
            assert intent_engine.needs_clarification(intent)
            assert intent.clarification_needed is not None
    
    @pytest.mark.asyncio
    async def test_emergency_detection(self, intent_engine, user_context):
        """Test that emergencies are detected"""
        with patch.object(intent_engine, 'client') as mock_client:
            mock_response = AsyncMock()
            mock_response.choices = [
                AsyncMock(message=AsyncMock(content='{"intent_type": "UNKNOWN", "items": [], "quantity": null, "confidence_score": 0.30, "urgency": "immediate", "clarification_needed": null, "raw_entities": {"emergency_detected": true}}'))
            ]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            intent = await intent_engine.parse_intent(
                "Mujhe bahut tez dard ho raha hai seene mein",
                user_context
            )
            
            assert intent.raw_entities.get("emergency_detected") == True


class TestNeedsClarification:
    
    def test_high_confidence_no_clarification(self, intent_engine):
        """High confidence should not need clarification"""
        intent = IntentSchema(
            intent_type=IntentType.ORDER_MEDICINE,
            items=["Shelcal"],
            confidence_score=0.92,
            urgency="standard"
        )
        assert not intent_engine.needs_clarification(intent)
    
    def test_low_confidence_needs_clarification(self, intent_engine):
        """Low confidence should need clarification"""
        intent = IntentSchema(
            intent_type=IntentType.ORDER_MEDICINE,
            items=[],
            confidence_score=0.65,
            urgency="standard"
        )
        assert intent_engine.needs_clarification(intent)
    
    def test_borderline_confidence(self, intent_engine):
        """Test borderline confidence (exactly at threshold)"""
        intent = IntentSchema(
            intent_type=IntentType.ORDER_MEDICINE,
            items=["Crocin"],
            confidence_score=0.85,
            urgency="standard"
        )
        # At exactly 0.85, should NOT need clarification (>= threshold)
        assert not intent_engine.needs_clarification(intent)


class TestSafeRefusal:
    
    def test_should_refuse_unknown_low_confidence(self, intent_engine):
        """Unknown intent with very low confidence should refuse"""
        intent = IntentSchema(
            intent_type=IntentType.UNKNOWN,
            items=[],
            confidence_score=0.30,
            urgency="standard"
        )
        assert intent_engine.should_refuse(intent)
    
    def test_should_not_refuse_known_intent(self, intent_engine):
        """Known intent should not refuse even with lower confidence"""
        intent = IntentSchema(
            intent_type=IntentType.ORDER_MEDICINE,
            items=["Shelcal"],
            confidence_score=0.75,
            urgency="standard"
        )
        assert not intent_engine.should_refuse(intent)