"""Usage limits and subscription management for SaberLink.

This module handles:
- PDF upload limits per user/subscription tier
- Text query limits per user/subscription tier
- Subscription validation through RevenueCat
- Usage tracking and enforcement
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


# Subscription tiers and their limits
SUBSCRIPTION_TIERS = {
    "free": {
        "pdf_uploads_per_month": 5,
        "text_queries_per_month": 20,
        "name": "Gratis",
        "description": "Perfecto para explorar SaberLink"
    },
    "pro_monthly": {
        "pdf_uploads_per_month": 50,
        "text_queries_per_month": 500,
        "name": "Pro Mensual",
        "description": "Para uso intensivo de investigación"
    },
    "pro_yearly": {
        "pdf_uploads_per_month": 100,
        "text_queries_per_month": 1000,
        "name": "Pro Anual",
        "description": "Mejor valor para investigación continua"
    }
}


class UsageLimits(BaseModel):
    """Usage limits for a subscription tier."""
    pdf_uploads_per_month: int
    text_queries_per_month: int
    name: str
    description: str


class UserUsage(BaseModel):
    """Track user's current usage."""
    user_id: str
    pdf_uploads_this_month: int = 0
    text_queries_this_month: int = 0
    current_tier: str = "free"
    last_reset: str = datetime.now().isoformat()
    subscription_expires: Optional[str] = None


class UsageTracker:
    """Track and enforce usage limits."""
    
    def __init__(self, storage_path: Path = None):
        if storage_path is None:
            from saberlink import config
            storage_path = config.PROCESSED_DIR / "usage_tracking.json"
        self.storage_path = storage_path
        self._ensure_storage()
    
    def _ensure_storage(self):
        """Ensure storage file exists."""
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text("{}")
    
    def _load_usage_data(self) -> dict:
        """Load usage data from storage."""
        try:
            return json.loads(self.storage_path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save_usage_data(self, data: dict):
        """Save usage data to storage."""
        self.storage_path.write_text(json.dumps(data, indent=2))
    
    def _reset_if_needed(self, user_usage: UserUsage) -> UserUsage:
        """Reset monthly counters if a new month has started."""
        last_reset = datetime.fromisoformat(user_usage.last_reset)
        now = datetime.now()
        
        # Reset if we're in a different month
        if (now.year, now.month) != (last_reset.year, last_reset.month):
            user_usage.pdf_uploads_this_month = 0
            user_usage.text_queries_this_month = 0
            user_usage.last_reset = now.isoformat()
        
        return user_usage
    
    def get_user_usage(self, user_id: str) -> UserUsage:
        """Get current usage for a user."""
        data = self._load_usage_data()
        user_data = data.get(user_id, {})
        
        usage = UserUsage(
            user_id=user_id,
            pdf_uploads_this_month=user_data.get("pdf_uploads_this_month", 0),
            text_queries_this_month=user_data.get("text_queries_this_month", 0),
            current_tier=user_data.get("current_tier", "free"),
            last_reset=user_data.get("last_reset", datetime.now().isoformat()),
            subscription_expires=user_data.get("subscription_expires")
        )
        
        return self._reset_if_needed(usage)
    
    def update_user_tier(self, user_id: str, tier: str, expires: Optional[str] = None):
        """Update user's subscription tier."""
        data = self._load_usage_data()
        
        if user_id not in data:
            data[user_id] = {}
        
        data[user_id]["current_tier"] = tier
        if expires:
            data[user_id]["subscription_expires"] = expires
        
        self._save_usage_data(data)
    
    def track_pdf_upload(self, user_id: str) -> bool:
        """Track a PDF upload and return True if within limits."""
        usage = self.get_user_usage(user_id)
        limits = SUBSCRIPTION_TIERS.get(usage.current_tier, SUBSCRIPTION_TIERS["free"])
        
        if usage.pdf_uploads_this_month >= limits["pdf_uploads_per_month"]:
            return False
        
        usage.pdf_uploads_this_month += 1
        self._save_usage_data({
            **self._load_usage_data(),
            user_id: usage.model_dump()
        })
        return True
    
    def track_text_query(self, user_id: str) -> bool:
        """Track a text query and return True if within limits."""
        usage = self.get_user_usage(user_id)
        limits = SUBSCRIPTION_TIERS.get(usage.current_tier, SUBSCRIPTION_TIERS["free"])
        
        if usage.text_queries_this_month >= limits["text_queries_per_month"]:
            return False
        
        usage.text_queries_this_month += 1
        self._save_usage_data({
            **self._load_usage_data(),
            user_id: usage.model_dump()
        })
        return True
    
    def get_remaining_usage(self, user_id: str) -> dict:
        """Get remaining usage for a user."""
        usage = self.get_user_usage(user_id)
        limits = SUBSCRIPTION_TIERS.get(usage.current_tier, SUBSCRIPTION_TIERS["free"])
        
        return {
            "tier": usage.current_tier,
            "tier_name": limits["name"],
            "pdf_uploads_remaining": max(0, limits["pdf_uploads_per_month"] - usage.pdf_uploads_this_month),
            "pdf_uploads_used": usage.pdf_uploads_this_month,
            "pdf_uploads_limit": limits["pdf_uploads_per_month"],
            "text_queries_remaining": max(0, limits["text_queries_per_month"] - usage.text_queries_this_month),
            "text_queries_used": usage.text_queries_this_month,
            "text_queries_limit": limits["text_queries_per_month"],
            "subscription_expires": usage.subscription_expires
        }


# Global usage tracker instance
_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """Get the global usage tracker instance."""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker


def check_subscription_status(user_id: str, revenuecat_data: dict) -> dict:
    """Validate subscription status from RevenueCat data.
    
    Args:
        user_id: User identifier
        revenuecat_data: Subscription data from RevenueCat SDK
        
    Returns:
        Dict with subscription status and tier information
    """
    tracker = get_usage_tracker()
    
    # Extract subscription info from RevenueCat data
    # RevenueCat typically provides: entitlements, subscriptions, etc.
    entitlements = revenuecat_data.get("entitlements", {})
    
    # Check for active subscription
    if "pro" in entitlements and entitlements["pro"].get("isActive", False):
        expiration = entitlements["pro"].get("expiresDate")
        # Determine if monthly or yearly based on product identifier
        product_id = entitlements["pro"].get("productIdentifier", "")
        
        if "yearly" in product_id.lower() or "annual" in product_id.lower():
            tier = "pro_yearly"
        else:
            tier = "pro_monthly"
        
        tracker.update_user_tier(user_id, tier, expiration)
    else:
        # No active subscription, default to free
        tracker.update_user_tier(user_id, "free", None)
    
    return tracker.get_remaining_usage(user_id)