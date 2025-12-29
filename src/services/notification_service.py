"""
Notification Service
Phase 5: Multi-Channel Confirmation
WhatsApp/SMS notifications to user and caregiver
"""

from typing import Optional
import httpx
from twilio.rest import Client as TwilioClient
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Multi-channel notification service
    Sends confirmations via SMS and WhatsApp
    """
    
    def __init__(self):
        self.twilio_client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.twilio_client = TwilioClient(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
        self.from_number = settings.TWILIO_PHONE_NUMBER
        
    async def send_sms(
        self,
        to_number: str,
        message: str
    ) -> bool:
        """
        Send SMS notification
        
        Args:
            to_number: Recipient phone number (with country code)
            message: Message text
            
        Returns:
            True if sent successfully
        """
        if not self.twilio_client:
            logger.warning("Twilio not configured, skipping SMS")
            return False
        
        try:
            # Ensure number has country code
            if not to_number.startswith('+'):
                to_number = f"+91{to_number}"  # Default to India
            
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(f"SMS sent to {to_number}: {message_obj.sid}")
            return True
            
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            return False
    
    async def send_whatsapp(
        self,
        to_number: str,
        message: str
    ) -> bool:
        """
        Send WhatsApp notification
        
        Args:
            to_number: Recipient phone number
            message: Message text
            
        Returns:
            True if sent successfully
        """
        if not self.twilio_client:
            logger.warning("Twilio not configured, skipping WhatsApp")
            return False
        
        try:
            # Format for WhatsApp
            if not to_number.startswith('+'):
                to_number = f"+91{to_number}"
            
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=f"whatsapp:{self.from_number}",
                to=f"whatsapp:{to_number}"
            )
            
            logger.info(f"WhatsApp sent to {to_number}: {message_obj.sid}")
            return True
            
        except Exception as e:
            logger.error(f"WhatsApp sending failed: {e}")
            return False
    
    async def send_order_confirmation(
        self,
        user_phone: str,
        caregiver_phone: Optional[str],
        order_number: str,
        amount: int,
        balance: int,
        delivery_time: str
    ):
        """
        Send order confirmation to user and caregiver
        Phase 5: Task 5.1 - Multi-Channel Confirmation
        """
        message = (
            f"✅ Sahayak Order Confirmed\n\n"
            f"Order: {order_number}\n"
            f"Amount: ₹{amount // 100}\n"
            f"Remaining Balance: ₹{balance // 100}\n"
            f"Expected Delivery: {delivery_time}\n\n"
            f"For help, call your caregiver."
        )
        
        # Send to user
        if settings.WHATSAPP_ENABLED:
            await self.send_whatsapp(user_phone, message)
        if settings.SMS_ENABLED:
            await self.send_sms(user_phone, message)
        
        # Send to caregiver if configured
        if caregiver_phone:
            caregiver_message = (
                f"📋 Sahayak - Caregiver Alert\n\n"
                f"Your family member placed an order:\n"
                f"Order: {order_number}\n"
                f"Amount: ₹{amount // 100}\n"
                f"Their Balance: ₹{balance // 100}\n"
                f"Delivery: {delivery_time}"
            )
            
            if settings.WHATSAPP_ENABLED:
                await self.send_whatsapp(caregiver_phone, caregiver_message)
            if settings.SMS_ENABLED:
                await self.send_sms(caregiver_phone, caregiver_message)
    
    async def send_low_balance_alert(
        self,
        caregiver_phone: str,
        user_name: str,
        balance: int
    ):
        """Alert caregiver when balance is low"""
        message = (
            f"⚠️ Sahayak - Low Balance Alert\n\n"
            f"{user_name}'s wallet balance is low: ₹{balance // 100}\n"
            f"Please add money to continue using Sahayak."
        )
        
        await self.send_whatsapp(caregiver_phone, message)
        await self.send_sms(caregiver_phone, message)