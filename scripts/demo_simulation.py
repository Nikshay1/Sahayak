"""
Demo Simulation Script
Phase 7: Task 7.2 - The Demo Script

Simulates the "Grandmother Test" conversation flow
Scene: Phone on speaker mode on a table. No laptop interaction.

Demo Script:
1. User: (Dials number) "Hello? Is this Sahayak?"
2. AI: "Namaste Sunita. Yes, I am here. How can I help you today?"
3. User: "Beta, my calcium medicines are finished. Can you send a new strip?"
4. AI: "I can see you usually order Shelcal 500. A strip of 15 costs 120 rupees. 
       Shall I order it to your home in Indiranagar?"
5. User: "Yes, please."
6. AI: "Done. I have paid 120 rupees from your wallet. Your new balance is 880 rupees.
       The chemist will deliver it by 5 PM."
"""

import asyncio
from datetime import datetime
from uuid import uuid4
import json

from src.core.intent_engine import IntentEngine, IntentSchema
from src.core.orchestrator import ExecutionOrchestrator
from src.wallet.ledger import WalletLedger
from src.adapters.pharmacy_adapter import MockPharmacyAdapter
from src.services.notification_service import NotificationService
from src.services.speech_to_text import TranscriptionEnhancer
from src.db.database import async_session_maker
from src.db.models import User
from src.schemas.logs import CallLogPacket
from src.config.constants import VoiceResponses


class DemoSimulator:
    """
    Simulates the complete demo flow for testing
    """
    
    def __init__(self):
        self.intent_engine = IntentEngine()
        self.transcription_enhancer = TranscriptionEnhancer()
        self.call_id = f"demo_{uuid4().hex[:8]}"
        
    async def run_demo(self):
        """Execute the full demo scenario"""
        
        print("\n" + "=" * 70)
        print("SAHAYAK DEMO - THE GRANDMOTHER TEST")
        print("=" * 70)
        print("Scenario: Sunita (78 years old) wants to order calcium tablets")
        print("Goal: Complete order without any technical assistance")
        print("=" * 70 + "\n")
        
        async with async_session_maker() as db:
            # Get demo user
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.phone_number == "+919876543210")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print("❌ Demo user not found. Run: python scripts/seed_demo_user.py")
                return
            
            print(f"📱 User: {user.full_name}")
            print(f"💰 Starting Balance: ₹{user.current_balance // 100}")
            print("-" * 70)
            
            # Initialize components
            wallet = WalletLedger(db)
            pharmacy = MockPharmacyAdapter()
            notifications = NotificationService()
            
            orchestrator = ExecutionOrchestrator(
                db_session=db,
                intent_engine=self.intent_engine,
                wallet_ledger=wallet,
                pharmacy_adapter=pharmacy,
                notification_service=notifications
            )
            
            # Create call log
            call_log = CallLogPacket(
                call_id=self.call_id,
                user_id=user.internal_id,
                call_started_at=datetime.now()
            )
            
            # Build user context
            user_context = await self._build_user_context(db, user)
            
            # Step 1: Greeting
            print("\n📞 [CALL CONNECTED]")
            await self._simulate_delay(1)
            
            print(f"\n👵 USER: \"Hello? Is this Sahayak?\"")
            await self._simulate_delay(1)
            
            greeting = VoiceResponses.GREETING.format(name=user.full_name.split()[0])
            print(f"\n🤖 SAHAYAK: \"{greeting}\"")
            await self._simulate_delay(2)
            
            # Step 2: User Request
            user_speech = "Beta, my calcium medicines are finished. Can you send a new strip?"
            print(f"\n👵 USER: \"{user_speech}\"")
            await self._simulate_delay(1)
            
            # Step 3: Process Intent
            print("\n   [Processing speech...]")
            enhanced_speech = self.transcription_enhancer.enhance(user_speech)
            
            intent = await self.intent_engine.parse_intent(
                transcript=enhanced_speech,
                user_context=user_context
            )
            
            print(f"   Intent: {intent.intent_type} (confidence: {intent.confidence_score:.2f})")
            print(f"   Items: {intent.items}")
            
            # Step 4: Orchestrator processes
            result = await orchestrator.process_intent(
                intent=intent,
                user_id=user.id,
                user_context=user_context,
                call_log=call_log
            )
            
            print(f"\n🤖 SAHAYAK: \"{result.voice_response}\"")
            await self._simulate_delay(3)
            
            if result.requires_confirmation:
                # Step 5: User Confirmation
                print(f"\n👵 USER: \"Yes, please.\"")
                await self._simulate_delay(1)
                
                # Step 6: Execute Order
                print("\n   [Processing order...]")
                
                final_result = await orchestrator.execute_confirmed_order(
                    confirmation_context=result.confirmation_context,
                    call_log=call_log
                )
                
                print(f"\n🤖 SAHAYAK: \"{final_result.voice_response}\"")
                
                if final_result.success:
                    print("\n" + "=" * 70)
                    print("✅ DEMO SUCCESSFUL - GRANDMOTHER TEST PASSED!")
                    print("=" * 70)
                    print(f"Order ID: {final_result.order_id}")
                    print(f"New Balance: ₹{final_result.new_balance // 100}")
                    print("=" * 70)
                else:
                    print("\n❌ Order failed:", final_result.error)
            
            # Print call log summary
            print("\n📋 CALL LOG SUMMARY:")
            print(json.dumps({
                "call_id": call_log.call_id,
                "intent_detected": call_log.intent_detected,
                "wallet_status": call_log.wallet_status,
                "execution_status": call_log.execution_status,
                "events_count": len(call_log.events)
            }, indent=2))
            
            await db.commit()
    
    async def run_balance_check_demo(self):
        """Demo for balance check scenario"""
        
        print("\n" + "=" * 70)
        print("SAHAYAK DEMO - BALANCE CHECK")
        print("=" * 70 + "\n")
        
        async with async_session_maker() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.phone_number == "+919876543210")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print("❌ Demo user not found.")
                return
            
            wallet = WalletLedger(db)
            
            orchestrator = ExecutionOrchestrator(
                db_session=db,
                intent_engine=self.intent_engine,
                wallet_ledger=wallet,
                pharmacy_adapter=MockPharmacyAdapter(),
                notification_service=NotificationService()
            )
            
            call_log = CallLogPacket(call_id=f"demo_bal_{uuid4().hex[:8]}")
            user_context = await self._build_user_context(db, user)
            
            # User asks for balance
            print(f"👵 USER: \"Kitne paise hain mere wallet mein?\"")
            
            intent = await self.intent_engine.parse_intent(
                transcript="Kitne paise hain mere wallet mein",
                user_context=user_context
            )
            
            print(f"   Intent: {intent.intent_type}")
            
            result = await orchestrator.process_intent(
                intent=intent,
                user_id=user.id,
                user_context=user_context,
                call_log=call_log
            )
            
            print(f"\n🤖 SAHAYAK: \"{result.voice_response}\"")
    
    async def run_clarification_demo(self):
        """Demo for clarification flow"""
        
        print("\n" + "=" * 70)
        print("SAHAYAK DEMO - CLARIFICATION FLOW")
        print("=" * 70 + "\n")
        
        async with async_session_maker() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(User).where(User.phone_number == "+919876543210")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print("❌ Demo user not found.")
                return
            
            user_context = await self._build_user_context(db, user)
            
            # Unclear request
            unclear_speech = "Woh dawai chahiye... woh jo main leti hoon..."
            print(f"👵 USER: \"{unclear_speech}\"")
            
            intent = await self.intent_engine.parse_intent(
                transcript=unclear_speech,
                user_context=user_context
            )
            
            print(f"   Intent: {intent.intent_type} (confidence: {intent.confidence_score:.2f})")
            print(f"   Clarification needed: {intent.clarification_needed}")
            
            if intent.confidence_score < 0.85:
                print(f"\n🤖 SAHAYAK: \"{VoiceResponses.CLARIFICATION_MEDICINE}\"")
                
                # User clarifies
                print(f"\n👵 USER: \"Shelcal. Calcium wali tablet.\"")
                
                intent2 = await self.intent_engine.parse_intent(
                    transcript="Shelcal. Calcium wali tablet.",
                    user_context=user_context
                )
                
                print(f"   Intent: {intent2.intent_type} (confidence: {intent2.confidence_score:.2f})")
                print(f"   Items: {intent2.items}")
    
    async def _build_user_context(self, db, user) -> dict:
        """Build user context for demo"""
        from sqlalchemy import select
        from src.db.models import UserMedicineHistory
        
        result = await db.execute(
            select(UserMedicineHistory)
            .where(UserMedicineHistory.user_id == user.id)
        )
        history = result.scalars().all()
        
        return {
            "internal_id": user.internal_id,
            "medicine_history": [
                {"name": h.medicine_name, "aliases": h.user_aliases}
                for h in history
            ],
            "address": user.city,
            "full_address": f"{user.address_line1}, {user.city} - {user.pincode}"
        }
    
    async def _simulate_delay(self, seconds: float):
        """Simulate realistic conversation delays"""
        await asyncio.sleep(seconds * 0.3)  # Speed up for demo


async def main():
    """Run demo simulations"""
    simulator = DemoSimulator()
    
    print("\n" + "=" * 70)
    print("SELECT DEMO SCENARIO:")
    print("1. Full Order Flow (Grandmother Test)")
    print("2. Balance Check")
    print("3. Clarification Flow")
    print("4. Run All Demos")
    print("=" * 70)
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        await simulator.run_demo()
    elif choice == "2":
        await simulator.run_balance_check_demo()
    elif choice == "3":
        await simulator.run_clarification_demo()
    elif choice == "4":
        await simulator.run_demo()
        await simulator.run_balance_check_demo()
        await simulator.run_clarification_demo()
    else:
        print("Invalid choice. Running full demo...")
        await simulator.run_demo()


if __name__ == "__main__":
    asyncio.run(main())