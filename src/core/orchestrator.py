"""
Execution Orchestrator
Phase 4: The "Agentic" Core
FIXED IMPORTS
"""

from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.core.intent_engine import IntentSchema, IntentEngine, MedicineResolver
from src.wallet.ledger import WalletLedger, WalletRulesEngine, InsufficientBalanceError
from src.adapters.pharmacy_adapter import MockPharmacyAdapter  # FIXED!
from src.services.notification_service import NotificationService
from src.config.constants import VoiceResponses, IntentType, LogEventType
from src.schemas.logs import CallLogPacket
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    """Result of orchestrator execution"""
    success: bool
    voice_response: str
    order_id: Optional[str] = None
    new_balance: Optional[int] = None
    requires_confirmation: bool = False
    confirmation_context: Optional[dict] = None
    error: Optional[str] = None


class ExecutionOrchestrator:
    """
    The Agentic Core - Orchestrates the entire flow from intent to execution
    
    Flow Logic:
    1. Input: User says "Order my heart medicine."
    2. Lookup: System finds "Atorvastatin" in user history.
    3. Price Check: API returns cost.
    4. Wallet Check: Wallet has enough. Lock amount.
    5. Voice Confirm: "The cost is X rupees. Should I proceed?"
    6. Execute: User says "Yes" → API POST → Wallet Debit.
    """
    
    def __init__(
        self,
        db_session,
        intent_engine: IntentEngine,
        wallet_ledger: WalletLedger,
        pharmacy_adapter: MockPharmacyAdapter,  # FIXED!
        notification_service: NotificationService
    ):
        self.db = db_session
        self.intent_engine = intent_engine
        self.wallet = wallet_ledger
        self.wallet_rules = WalletRulesEngine()
        self.pharmacy = pharmacy_adapter
        self.notifications = notification_service
        self.medicine_resolver = MedicineResolver(db_session)
        
    async def process_intent(
        self,
        intent: IntentSchema,
        user_id: UUID,
        user_context: dict,
        call_log: CallLogPacket
    ) -> OrchestratorResult:
        """Main orchestration entry point"""
        
        # Check if we should safely refuse
        if self.intent_engine.should_refuse(intent):
            call_log.add_event(LogEventType.INTENT_DETECTED, {
                "intent": IntentType.UNKNOWN,
                "action": "SAFE_REFUSAL"
            })
            return OrchestratorResult(
                success=False,
                voice_response=VoiceResponses.SAFE_REFUSAL
            )
        
        # Route by intent type
        if intent.intent_type == IntentType.ORDER_MEDICINE:
            return await self._handle_order_medicine(intent, user_id, user_context, call_log)
        
        elif intent.intent_type == IntentType.CHECK_BALANCE:
            return await self._handle_check_balance(user_id, user_context, call_log)
        
        elif intent.intent_type == IntentType.ORDER_STATUS:
            return await self._handle_order_status(user_id, user_context, call_log)
        
        else:
            # Check for emergency keywords
            if intent.raw_entities.get("emergency_detected"):
                return OrchestratorResult(
                    success=False,
                    voice_response=VoiceResponses.EMERGENCY_REDIRECT
                )
            
            return OrchestratorResult(
                success=False,
                voice_response=VoiceResponses.UNSUPPORTED_ACTION
            )
    
    async def _handle_order_medicine(
        self,
        intent: IntentSchema,
        user_id: UUID,
        user_context: dict,
        call_log: CallLogPacket
    ) -> OrchestratorResult:
        """Handle medicine ordering flow"""
        
        # Step 1: Check if clarification needed
        if self.intent_engine.needs_clarification(intent):
            clarification_prompt = self._get_clarification_prompt(intent)
            call_log.add_event(LogEventType.CLARIFICATION_REQUESTED, {
                "reason": intent.clarification_needed,
                "confidence": intent.confidence_score
            })
            return OrchestratorResult(
                success=False,
                voice_response=clarification_prompt,
                requires_confirmation=True,
                confirmation_context={"type": "clarification", "original_intent": intent.dict()}
            )
        
        # Step 2: Resolve medicines
        internal_id = user_context.get("internal_id")
        resolved_medicines = await self.medicine_resolver.resolve(intent.items, internal_id)
        
        unmatched = [m for m in resolved_medicines if not m.get("matched", True)]
        if unmatched:
            return OrchestratorResult(
                success=False,
                voice_response=VoiceResponses.CLARIFICATION_MEDICINE,
                requires_confirmation=True,
                confirmation_context={"type": "medicine_clarification", "unmatched": unmatched}
            )
        
        # Step 3: Check availability and get pricing
        total_price = 0
        items_detail = []
        
        for medicine in resolved_medicines:
            availability = await self.pharmacy.check_availability(medicine["sku"])
            if not availability.get("available", False):
                return OrchestratorResult(
                    success=False,
                    voice_response=f"I'm sorry, {medicine['name']} is not available right now. "
                                   "Should I check with another pharmacy?"
                )
            
            quantity = intent.quantity or medicine.get("typical_quantity", 1)
            item_price = availability.get("price", medicine.get("price", 0)) * quantity
            total_price += item_price
            
            items_detail.append({
                "name": medicine["name"],
                "sku": medicine["sku"],
                "quantity": quantity,
                "price": item_price
            })
        
        call_log.add_event(LogEventType.WALLET_CHECKED, {
            "required_amount": total_price
        })
        
        # Step 4: Wallet check
        current_balance, locked_balance = await self.wallet.get_balance(user_id)
        is_valid, error = self.wallet_rules.validate_transaction(
            total_price, current_balance, locked_balance
        )
        
        if not is_valid:
            if "Insufficient" in str(error):
                return OrchestratorResult(
                    success=False,
                    voice_response=VoiceResponses.INSUFFICIENT_BALANCE.format(
                        balance=current_balance // 100,
                        amount=total_price // 100
                    )
                )
            return OrchestratorResult(success=False, voice_response=str(error))
        
        # Step 5: Return confirmation request (NOT executing yet)
        medicine_names = ", ".join([m["name"] for m in items_detail])
        address = user_context.get("address", "your home")
        
        confirmation_response = VoiceResponses.ORDER_CONFIRMATION.format(
            medicine=medicine_names,
            quantity=sum(m["quantity"] for m in items_detail),
            price=total_price // 100,
            address=address
        )
        
        return OrchestratorResult(
            success=True,
            voice_response=confirmation_response,
            requires_confirmation=True,
            confirmation_context={
                "type": "order_confirmation",
                "items": items_detail,
                "total_price": total_price,
                "user_id": str(user_id),
                "address": user_context.get("full_address")
            }
        )
    
    async def execute_confirmed_order(
        self,
        confirmation_context: dict,
        call_log: CallLogPacket
    ) -> OrchestratorResult:
        """Execute order after user confirms"""
        from uuid import UUID as UUIDType
        from src.db.models import Order
        
        user_id = UUIDType(confirmation_context["user_id"])
        items = confirmation_context["items"]
        total_price = confirmation_context["total_price"]
        address = confirmation_context["address"]
        
        # Create order record
        order = Order(
            order_number=f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}",
            user_id=user_id,
            items=items,
            total_amount=total_price,
            delivery_address=address,
            estimated_delivery=datetime.now() + timedelta(hours=4)
        )
        self.db.add(order)
        await self.db.flush()
        
        # Step 1: Lock funds
        try:
            transaction_id = await self.wallet.check_and_lock(
                user_id=user_id,
                amount=total_price,
                reference_id=order.id,
                description=f"Order {order.order_number}"
            )
            order.transaction_id = transaction_id
            call_log.add_event(LogEventType.WALLET_LOCKED, {
                "amount": total_price,
                "transaction_id": transaction_id
            })
        except InsufficientBalanceError as e:
            return OrchestratorResult(
                success=False,
                voice_response=VoiceResponses.INSUFFICIENT_BALANCE.format(
                    balance=0, amount=total_price // 100
                ),
                error=str(e)
            )
        
        # Step 2: Call pharmacy API
        try:
            pharmacy_result = await self.pharmacy.place_order(address, items)
            
            if pharmacy_result.get("success"):
                # Step 3: Confirm the debit
                await self.wallet.confirm_debit(transaction_id, user_id)
                
                order.external_order_id = pharmacy_result.get("order_id")
                order.execution_status = "SUCCESS"
                
                call_log.add_event(LogEventType.WALLET_DEBITED, {
                    "amount": total_price,
                    "transaction_id": transaction_id
                })
                call_log.add_event(LogEventType.ORDER_PLACED, {
                    "order_id": order.order_number,
                    "external_id": pharmacy_result.get("order_id")
                })
                
                # Get new balance for feedback
                new_balance, _ = await self.wallet.get_balance(user_id)
                
                delivery_time = order.estimated_delivery.strftime("%I %p")
                
                return OrchestratorResult(
                    success=True,
                    voice_response=VoiceResponses.ORDER_COMPLETE.format(
                        amount=total_price // 100,
                        balance=new_balance // 100,
                        delivery_time=delivery_time
                    ),
                    order_id=order.order_number,
                    new_balance=new_balance
                )
            else:
                raise Exception(pharmacy_result.get("error", "Unknown pharmacy error"))
                
        except Exception as e:
            # Step 4 (Failure): Auto-refund
            logger.error(f"Order execution failed: {e}")
            
            await self.wallet.auto_refund(
                transaction_id=transaction_id,
                user_id=user_id,
                reason=str(e)
            )
            
            order.execution_status = "FAILED"
            
            call_log.add_event(LogEventType.ORDER_FAILED, {
                "error": str(e),
                "refunded": True
            })
            call_log.add_event(LogEventType.WALLET_REFUNDED, {
                "amount": total_price,
                "transaction_id": transaction_id
            })
            
            return OrchestratorResult(
                success=False,
                voice_response=VoiceResponses.API_ERROR,
                error=str(e)
            )
    
    async def _handle_check_balance(
        self,
        user_id: UUID,
        user_context: dict,
        call_log: CallLogPacket
    ) -> OrchestratorResult:
        """Handle balance check request"""
        
        current_balance, locked_balance = await self.wallet.get_balance(user_id)
        available = current_balance - locked_balance
        
        # Estimate orders (assuming avg order is ₹150)
        avg_order = 15000  # paise
        estimate = available // avg_order
        
        call_log.add_event(LogEventType.WALLET_CHECKED, {
            "balance": current_balance,
            "available": available
        })
        
        return OrchestratorResult(
            success=True,
            voice_response=VoiceResponses.BALANCE_CHECK.format(
                balance=available // 100,
                estimate=max(estimate, 0)
            ),
            new_balance=available
        )
    
    async def _handle_order_status(
        self,
        user_id: UUID,
        user_context: dict,
        call_log: CallLogPacket
    ) -> OrchestratorResult:
        """Handle order status check"""
        return OrchestratorResult(
            success=True,
            voice_response="Your last order is being prepared and will be delivered soon."
        )
    
    def _get_clarification_prompt(self, intent: IntentSchema) -> str:
        """Get appropriate clarification prompt based on what's unclear"""
        if intent.clarification_needed == "medicine_name":
            return VoiceResponses.CLARIFICATION_MEDICINE
        elif intent.clarification_needed == "quantity":
            return VoiceResponses.CLARIFICATION_QUANTITY.format(
                medicine=intent.items[0] if intent.items else "the medicine"
            )
        else:
            return VoiceResponses.SAFE_REFUSAL