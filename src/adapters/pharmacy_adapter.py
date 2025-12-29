"""
Partner API Adapter
Phase 4: Task 4.1 - Sahayak acts as a bridge to the real world
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import httpx
import asyncio
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)


@dataclass
class AvailabilityResult:
    """Result of availability check"""
    available: bool
    price: int  # In paise
    stock_quantity: Optional[int] = None
    estimated_delivery: Optional[str] = None


@dataclass  
class OrderResult:
    """Result of order placement"""
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    estimated_delivery: Optional[str] = None


class BasePharmacyAdapter(ABC):
    """
    Base adapter interface for pharmacy partners
    Architecture treats this as a real external HTTP request
    """
    
    @abstractmethod
    async def check_availability(self, sku: str) -> dict:
        """
        Check inventory for a medicine
        
        Args:
            sku: Medicine SKU
            
        Returns:
            Dict with availability info
        """
        pass
    
    @abstractmethod
    async def place_order(self, user_address: str, items: List[dict]) -> dict:
        """
        Execute the trade / place the order
        
        Args:
            user_address: Delivery address
            items: List of items with sku, quantity
            
        Returns:
            Dict with order result
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict:
        """
        Get status of an existing order
        
        Args:
            order_id: External order ID
            
        Returns:
            Dict with status info
        """
        pass


class MockPharmacyAdapter(BasePharmacyAdapter):
    """
    Mock Pharmacy API for MVP
    Simulates real pharmacy behavior for demo purposes
    """
    
    def __init__(self):
        # Mock medicine catalog
        self.catalog = {
            "SHELCAL500": {
                "name": "Shelcal 500",
                "price": 12000,  # ₹120 in paise
                "stock": 100,
                "units_per_strip": 15
            },
            "ATORVA10": {
                "name": "Atorvastatin 10mg",
                "price": 8500,
                "stock": 50,
                "units_per_strip": 10
            },
            "METFORM500": {
                "name": "Metformin 500mg",
                "price": 4500,
                "stock": 200,
                "units_per_strip": 10
            },
            "AMLO5": {
                "name": "Amlodipine 5mg",
                "price": 6000,
                "stock": 75,
                "units_per_strip": 10
            },
            "CROCIN500": {
                "name": "Crocin 500mg",
                "price": 2500,
                "stock": 500,
                "units_per_strip": 15
            },
            "PANTOP40": {
                "name": "Pantoprazole 40mg",
                "price": 9000,
                "stock": 80,
                "units_per_strip": 10
            },
            "THYRONORM50": {
                "name": "Thyronorm 50mcg",
                "price": 11000,
                "stock": 60,
                "units_per_strip": 100
            }
        }
        
        self.orders = {}  # In-memory order storage for mock
        
    async def check_availability(self, sku: str) -> dict:
        """Check if medicine is available"""
        # Simulate network latency
        await asyncio.sleep(0.2)
        
        if sku not in self.catalog:
            return {
                "available": False,
                "error": "Medicine not found in catalog"
            }
        
        medicine = self.catalog[sku]
        
        return {
            "available": medicine["stock"] > 0,
            "price": medicine["price"],
            "stock_quantity": medicine["stock"],
            "name": medicine["name"],
            "units_per_strip": medicine["units_per_strip"],
            "estimated_delivery": "4 hours"
        }
    
    async def place_order(self, user_address: str, items: List[dict]) -> dict:
        """Place order with mock pharmacy"""
        # Simulate network latency
        await asyncio.sleep(0.5)
        
        # Simulate occasional failures (5% failure rate for realism)
        import random
        if random.random() < 0.05:
            return {
                "success": False,
                "error": "Pharmacy system temporarily unavailable"
            }
        
        # Validate all items
        total = 0
        order_items = []
        
        for item in items:
            sku = item.get("sku")
            quantity = item.get("quantity", 1)
            
            if sku not in self.catalog:
                return {
                    "success": False,
                    "error": f"Medicine {sku} not found"
                }
            
            medicine = self.catalog[sku]
            if medicine["stock"] < quantity:
                return {
                    "success": False,
                    "error": f"Insufficient stock for {medicine['name']}"
                }
            
            item_total = medicine["price"] * quantity
            total += item_total
            
            order_items.append({
                "sku": sku,
                "name": medicine["name"],
                "quantity": quantity,
                "price": item_total
            })
            
            # Reduce mock stock
            self.catalog[sku]["stock"] -= quantity
        
        # Generate order ID
        order_id = f"PH{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
        
        estimated_delivery = datetime.now() + timedelta(hours=4)
        
        # Store order
        self.orders[order_id] = {
            "order_id": order_id,
            "items": order_items,
            "total": total,
            "address": user_address,
            "status": "CONFIRMED",
            "estimated_delivery": estimated_delivery,
            "created_at": datetime.now()
        }
        
        logger.info(f"Mock order placed: {order_id}, total: ₹{total/100}")
        
        return {
            "success": True,
            "order_id": order_id,
            "total": total,
            "estimated_delivery": estimated_delivery.strftime("%I:%M %p"),
            "items": order_items
        }
    
    async def get_order_status(self, order_id: str) -> dict:
        """Get order status"""
        await asyncio.sleep(0.1)
        
        if order_id not in self.orders:
            return {
                "found": False,
                "error": "Order not found"
            }
        
        order = self.orders[order_id]
        
        # Simulate order progression
        hours_since_order = (datetime.now() - order["created_at"]).total_seconds() / 3600
        
        if hours_since_order < 0.5:
            status = "PROCESSING"
        elif hours_since_order < 2:
            status = "DISPATCHED"
        elif hours_since_order < 4:
            status = "OUT_FOR_DELIVERY"
        else:
            status = "DELIVERED"
        
        return {
            "found": True,
            "order_id": order_id,
            "status": status,
            "items": order["items"],
            "estimated_delivery": order["estimated_delivery"].strftime("%I:%M %p")
        }


class RealPharmacyAdapter(BasePharmacyAdapter):
    """
    Real Pharmacy API Adapter
    Template for connecting to actual pharmacy partners
    """
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
    
    async def check_availability(self, sku: str) -> dict:
        """Check availability via real API"""
        try:
            response = await self.client.get(
                f"/inventory/{sku}",
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "available": data.get("in_stock", False),
                "price": int(data.get("price", 0) * 100),  # Convert to paise
                "stock_quantity": data.get("quantity"),
                "name": data.get("name"),
                "estimated_delivery": data.get("delivery_estimate")
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Pharmacy API error: {e}")
            return {"available": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Pharmacy API connection error: {e}")
            return {"available": False, "error": "Service unavailable"}
    
    async def place_order(self, user_address: str, items: List[dict]) -> dict:
        """Place order via real API"""
        try:
            payload = {
                "delivery_address": user_address,
                "items": [
                    {"sku": item["sku"], "quantity": item["quantity"]}
                    for item in items
                ],
                "payment_confirmed": True  # We've already locked funds
            }
            
            response = await self.client.post("/orders", json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "order_id": data.get("order_id"),
                "estimated_delivery": data.get("estimated_delivery")
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Order placement failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return {"success": False, "error": "Service unavailable"}
    
    async def get_order_status(self, order_id: str) -> dict:
        """Get order status via real API"""
        try:
            response = await self.client.get(f"/orders/{order_id}")
            response.raise_for_status()
            return {"found": True, **response.json()}
        except Exception as e:
            return {"found": False, "error": str(e)}
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


def get_pharmacy_adapter() -> BasePharmacyAdapter:
    """Factory function to get appropriate adapter"""
    if settings.ENVIRONMENT == "production":
        return RealPharmacyAdapter(
            base_url=settings.PHARMACY_API_URL,
            api_key=settings.PHARMACY_API_KEY
        )
    return MockPharmacyAdapter()