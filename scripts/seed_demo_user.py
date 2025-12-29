"""
Demo User Setup
Phase 7: Task 7.1 - User Setup for "Grandmother Test"

Persona: "Sunita", 78 years old
Context: Lives alone. Needs calcium tablets.
Wallet: Pre-loaded with ₹1000
"""

import asyncio
from uuid import uuid4
from datetime import datetime

from src.db.database import async_session_maker
from src.db.models import User, UserMedicineHistory, LedgerEntry, TransactionType, MedicineCatalog
from src.utils.privacy import PIIRedactor


async def seed_demo_data():
    """Create demo user and data for Phase 7 demo"""
    
    async with async_session_maker() as db:
        pii_redactor = PIIRedactor()
        
        # Check if demo user exists
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.phone_number == "+919876543210")
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"Demo user already exists: {existing_user.internal_id}")
            return existing_user
        
        # Create demo user - "Sunita"
        user_id = uuid4()
        internal_id = pii_redactor.generate_internal_id("+919876543210")
        
        demo_user = User(
            id=user_id,
            internal_id=internal_id,
            phone_number="+919876543210",
            full_name="Sunita Sharma",
            address_line1="42, Gandhi Nagar",
            address_line2="Near City Hospital",
            city="Indiranagar",
            pincode="560038",
            caregiver_phone="+919876543211",
            caregiver_name="Rahul Sharma",
            current_balance=100000,  # ₹1000 in paise
            locked_balance=0,
            preferred_language="hi"
        )
        
        db.add(demo_user)
        
        # Add initial wallet credit
        initial_credit = LedgerEntry(
            transaction_id=f"txn_initial_{uuid4().hex[:8]}",
            user_id=user_id,
            amount=100000,
            transaction_type=TransactionType.CREDIT,
            reference_type="INITIAL_TOPUP",
            balance_after=100000,
            description="Initial wallet setup by caregiver"
        )
        db.add(initial_credit)
        
        # Add medicine history
        medicines = [
            {
                "name": "Shelcal 500",
                "sku": "SHELCAL500",
                "generic_name": "Calcium Carbonate",
                "aliases": ["calcium tablet", "calcium wali", "haddi ki dawai", "shelcal"],
                "typical_quantity": 1
            },
            {
                "name": "Atorvastatin 10mg",
                "sku": "ATORVA10",
                "generic_name": "Atorvastatin",
                "aliases": ["heart medicine", "heart ki dawai", "cholesterol ki goli"],
                "typical_quantity": 1
            },
            {
                "name": "Thyronorm 50mcg",
                "sku": "THYRONORM50",
                "generic_name": "Levothyroxine",
                "aliases": ["thyroid ki dawai", "thyroid tablet"],
                "typical_quantity": 1
            }
        ]
        
        for med in medicines:
            history = UserMedicineHistory(
                user_id=user_id,
                medicine_name=med["name"],
                medicine_sku=med["sku"],
                generic_name=med["generic_name"],
                user_aliases=med["aliases"],
                typical_quantity=med["typical_quantity"],
                order_count=5,
                last_ordered=datetime.now()
            )
            db.add(history)
        
        # Seed medicine catalog
        catalog_items = [
            {
                "sku": "SHELCAL500",
                "name": "Shelcal 500",
                "generic_name": "Calcium Carbonate + Vitamin D3",
                "aliases": ["calcium", "calcium tablet", "shelcal", "haddi ki dawai"],
                "price_per_unit": 12000,  # ₹120
                "units_per_strip": 15,
                "category": "supplements"
            },
            {
                "sku": "ATORVA10",
                "name": "Atorvastatin 10mg",
                "generic_name": "Atorvastatin",
                "aliases": ["heart medicine", "cholesterol tablet", "atorva"],
                "price_per_unit": 8500,
                "units_per_strip": 10,
                "category": "cardiac"
            },
            {
                "sku": "METFORM500",
                "name": "Metformin 500mg",
                "generic_name": "Metformin",
                "aliases": ["sugar ki dawai", "diabetes tablet", "metformin"],
                "price_per_unit": 4500,
                "units_per_strip": 10,
                "category": "diabetes"
            },
            {
                "sku": "CROCIN500",
                "name": "Crocin 500mg",
                "generic_name": "Paracetamol",
                "aliases": ["bukhar ki dawai", "dard ki goli", "crocin", "fever tablet"],
                "price_per_unit": 2500,
                "units_per_strip": 15,
                "category": "pain_relief"
            },
            {
                "sku": "THYRONORM50",
                "name": "Thyronorm 50mcg",
                "generic_name": "Levothyroxine",
                "aliases": ["thyroid", "thyroid ki dawai"],
                "price_per_unit": 11000,
                "units_per_strip": 100,
                "category": "thyroid"
            }
        ]
        
        for item in catalog_items:
            # Check if exists
            existing = await db.execute(
                select(MedicineCatalog).where(MedicineCatalog.sku == item["sku"])
            )
            if not existing.scalar_one_or_none():
                catalog_entry = MedicineCatalog(**item)
                db.add(catalog_entry)
        
        await db.commit()
        
        print("=" * 60)
        print("DEMO USER CREATED")
        print("=" * 60)
        print(f"Name: Sunita Sharma")
        print(f"Phone: +91 98765 43210")
        print(f"Internal ID: {internal_id}")
        print(f"Wallet Balance: ₹1000")
        print(f"Address: 42, Gandhi Nagar, Indiranagar - 560038")
        print(f"Caregiver: Rahul Sharma (+91 98765 43211)")
        print("=" * 60)
        print("Medicine History:")
        for med in medicines:
            print(f"  - {med['name']} (aliases: {', '.join(med['aliases'][:2])})")
        print("=" * 60)
        
        return demo_user


async def reset_demo_wallet():
    """Reset demo user's wallet to ₹1000"""
    async with async_session_maker() as db:
        from sqlalchemy import select, update
        
        result = await db.execute(
            select(User).where(User.phone_number == "+919876543210")
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Reset balance
            user.current_balance = 100000
            user.locked_balance = 0
            
            # Add reset ledger entry
            reset_entry = LedgerEntry(
                transaction_id=f"txn_reset_{uuid4().hex[:8]}",
                user_id=user.id,
                amount=100000,
                transaction_type=TransactionType.CREDIT,
                reference_type="DEMO_RESET",
                balance_after=100000,
                description="Demo wallet reset"
            )
            db.add(reset_entry)
            
            await db.commit()
            print(f"Wallet reset to ₹1000 for user {user.internal_id}")
        else:
            print("Demo user not found. Run seed_demo_data() first.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        asyncio.run(reset_demo_wallet())
    else:
        asyncio.run(seed_demo_data())