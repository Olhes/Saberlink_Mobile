"""Usage limits and subscription management for SaberLink.

This module provides the API layer for usage tracking and subscription management.
It follows the modular architecture pattern: can be deleted without breaking core functionality.

This module delegates to the saberlink.payments module for business logic,
maintaining separation of concerns between API and business logic.
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime

# Subscription tiers and their limits (API-facing constants)
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


def check_subscription_status(user_id: str, revenuecat_data: dict) -> dict:
    """Validate subscription status from RevenueCat data.
    
    This API layer function delegates to the payments module for business logic.
    
    Args:
        user_id: User identifier
        revenuecat_data: Subscription data from RevenueCat SDK
        
    Returns:
        Dict with subscription status and tier information
    """
    try:
        from saberlink.payments import process_subscription_update
        
        # Delegate to payments module for business logic
        result = process_subscription_update(user_id, revenuecat_data)
        
        # Format result for API response
        return {
            "tier": result["current_tier"],
            "tier_name": SUBSCRIPTION_TIERS.get(result["current_tier"], SUBSCRIPTION_TIERS["free"])["name"],
            "pdf_uploads_remaining": max(0, SUBSCRIPTION_TIERS.get(result["current_tier"], SUBSCRIPTION_TIERS["free"])["pdf_uploads_per_month"] - result["pdf_uploads_used"]),
            "pdf_uploads_used": result["pdf_uploads_used"],
            "pdf_uploads_limit": SUBSCRIPTION_TIERS.get(result["current_tier"], SUBSCRIPTION_TIERS["free"])["pdf_uploads_per_month"],
            "text_queries_remaining": max(0, SUBSCRIPTION_TIERS.get(result["current_tier"], SUBSCRIPTION_TIERS["free"])["text_queries_per_month"] - result["text_queries_used"]),
            "text_queries_used": result["text_queries_used"],
            "text_queries_limit": SUBSCRIPTION_TIERS.get(result["current_tier"], SUBSCRIPTION_TIERS["free"])["text_queries_per_month"],
            "subscription_expires": result["subscription_expires"]
        }
    except ImportError:
        # Fallback if payments module is not available
        return _fallback_subscription_status(user_id, revenuecat_data)


def _fallback_subscription_status(user_id: str, revenuecat_data: dict) -> dict:
    """Fallback implementation when payments module is not available.
    
    This ensures the API remains functional even if the payments module is deleted,
    following the modular architecture principle.
    """
    from saberlink import config
    from pathlib import Path
    import json
    
    usage_file = config.PROCESSED_DIR / "usage_tracking.json"
    
    try:
        if usage_file.exists():
            data = json.loads(usage_file.read_text())
            user_data = data.get(user_id, {})
            
            # Process RevenueCat data
            entitlements = revenuecat_data.get("entitlements", {})
            if "pro" in entitlements and entitlements["pro"].get("isActive", False):
                product_id = entitlements["pro"].get("productIdentifier", "")
                tier = "pro_yearly" if "yearly" in product_id.lower() else "pro_monthly"
                expiration = entitlements["pro"].get("expiresDate")
            else:
                tier = "free"
                expiration = None
            
            # Update user data
            if user_id not in data:
                data[user_id] = {}
            data[user_id]["current_tier"] = tier
            data[user_id]["subscription_expires"] = expiration
            usage_file.write_text(json.dumps(data, indent=2))
            
            # Return formatted result
            tier_limits = SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["free"])
            return {
                "tier": tier,
                "tier_name": tier_limits["name"],
                "pdf_uploads_remaining": max(0, tier_limits["pdf_uploads_per_month"] - user_data.get("pdf_uploads_this_month", 0)),
                "pdf_uploads_used": user_data.get("pdf_uploads_this_month", 0),
                "pdf_uploads_limit": tier_limits["pdf_uploads_per_month"],
                "text_queries_remaining": max(0, tier_limits["text_queries_per_month"] - user_data.get("text_queries_this_month", 0)),
                "text_queries_used": user_data.get("text_queries_this_month", 0),
                "text_queries_limit": tier_limits["text_queries_per_month"],
                "subscription_expires": expiration
            }
    except Exception:
        pass
    
    # Return default free tier
    return {
        "tier": "free",
        "tier_name": SUBSCRIPTION_TIERS["free"]["name"],
        "pdf_uploads_remaining": SUBSCRIPTION_TIERS["free"]["pdf_uploads_per_month"],
        "pdf_uploads_used": 0,
        "pdf_uploads_limit": SUBSCRIPTION_TIERS["free"]["pdf_uploads_per_month"],
        "text_queries_remaining": SUBSCRIPTION_TIERS["free"]["text_queries_per_month"],
        "text_queries_used": 0,
        "text_queries_limit": SUBSCRIPTION_TIERS["free"]["text_queries_per_month"],
        "subscription_expires": None
    }


def track_usage(user_id: str, action_type: str) -> bool:
    """Track usage for a specific action.
    
    This API layer function delegates to the payments module for business logic.
    
    Args:
        user_id: User identifier
        action_type: "pdf_upload" or "text_query"
        
    Returns:
        True if usage was tracked successfully, False if limit reached
    """
    try:
        from saberlink.payments import track_usage as payments_track_usage
        return payments_track_usage(user_id, action_type)
    except ImportError:
        # Fallback implementation
        return _fallback_track_usage(user_id, action_type)


def _fallback_track_usage(user_id: str, action_type: str) -> bool:
    """Fallback implementation when payments module is not available."""
    from saberlink import config
    from pathlib import Path
    import json
    
    usage_file = config.PROCESSED_DIR / "usage_tracking.json"
    
    # Check limits first
    try:
        if usage_file.exists():
            data = json.loads(usage_file.read_text())
            user_data = data.get(user_id, {})
            current_tier = user_data.get("current_tier", "free")
            tier_limits = SUBSCRIPTION_TIERS.get(current_tier, SUBSCRIPTION_TIERS["free"])
            
            if action_type == "pdf_upload":
                used = user_data.get("pdf_uploads_this_month", 0)
                if used >= tier_limits["pdf_uploads_per_month"]:
                    return False
            elif action_type == "text_query":
                used = user_data.get("text_queries_this_month", 0)
                if used >= tier_limits["text_queries_per_month"]:
                    return False
    except Exception:
        pass
    
    # Track usage
    try:
        if not usage_file.exists():
            usage_file.parent.mkdir(parents=True, exist_ok=True)
            usage_file.write_text("{}")
        
        data = json.loads(usage_file.read_text())
        
        if user_id not in data:
            data[user_id] = {}
        
        # Reset counters if new month
        last_reset = data[user_id].get("last_reset")
        if last_reset:
            last_reset_date = datetime.fromisoformat(last_reset)
            now = datetime.now()
            if (now.year, now.month) != (last_reset_date.year, last_reset_date.month):
                data[user_id]["pdf_uploads_this_month"] = 0
                data[user_id]["text_queries_this_month"] = 0
                data[user_id]["last_reset"] = now.isoformat()
        
        # Increment counter
        if action_type == "pdf_upload":
            data[user_id]["pdf_uploads_this_month"] = data[user_id].get("pdf_uploads_this_month", 0) + 1
        elif action_type == "text_query":
            data[user_id]["text_queries_this_month"] = data[user_id].get("text_queries_this_month", 0) + 1
        
        usage_file.write_text(json.dumps(data, indent=2))
        return True
    except Exception:
        return False


def get_user_usage(user_id: str) -> dict:
    """Get current usage for a user.
    
    This API layer function delegates to the payments module for business logic.
    
    Args:
        user_id: User identifier
        
    Returns:
        Dict with current usage information
    """
    try:
        from saberlink.payments import validate_subscription
        result = validate_subscription(user_id)
        
        # Format result for API response
        tier_limits = SUBSCRIPTION_TIERS.get(result["current_tier"], SUBSCRIPTION_TIERS["free"])
        return {
            "tier": result["current_tier"],
            "tier_name": tier_limits["name"],
            "pdf_uploads_remaining": max(0, tier_limits["pdf_uploads_per_month"] - result["pdf_uploads_used"]),
            "pdf_uploads_used": result["pdf_uploads_used"],
            "pdf_uploads_limit": tier_limits["pdf_uploads_per_month"],
            "text_queries_remaining": max(0, tier_limits["text_queries_per_month"] - result["text_queries_used"]),
            "text_queries_used": result["text_queries_used"],
            "text_queries_limit": tier_limits["text_queries_per_month"],
            "subscription_expires": result["subscription_expires"]
        }
    except ImportError:
        # Fallback implementation
        return _fallback_get_user_usage(user_id)


def _fallback_get_user_usage(user_id: str) -> dict:
    """Fallback implementation when payments module is not available."""
    from saberlink import config
    from pathlib import Path
    import json
    
    usage_file = config.PROCESSED_DIR / "usage_tracking.json"
    
    try:
        if usage_file.exists():
            data = json.loads(usage_file.read_text())
            user_data = data.get(user_id, {})
            current_tier = user_data.get("current_tier", "free")
            tier_limits = SUBSCRIPTION_TIERS.get(current_tier, SUBSCRIPTION_TIERS["free"])
            
            return {
                "tier": current_tier,
                "tier_name": tier_limits["name"],
                "pdf_uploads_remaining": max(0, tier_limits["pdf_uploads_per_month"] - user_data.get("pdf_uploads_this_month", 0)),
                "pdf_uploads_used": user_data.get("pdf_uploads_this_month", 0),
                "pdf_uploads_limit": tier_limits["pdf_uploads_per_month"],
                "text_queries_remaining": max(0, tier_limits["text_queries_per_month"] - user_data.get("text_queries_this_month", 0)),
                "text_queries_used": user_data.get("text_queries_this_month", 0),
                "text_queries_limit": tier_limits["text_queries_per_month"],
                "subscription_expires": user_data.get("subscription_expires")
            }
    except Exception:
        pass
    
    # Return default free tier
    return {
        "tier": "free",
        "tier_name": SUBSCRIPTION_TIERS["free"]["name"],
        "pdf_uploads_remaining": SUBSCRIPTION_TIERS["free"]["pdf_uploads_per_month"],
        "pdf_uploads_used": 0,
        "pdf_uploads_limit": SUBSCRIPTION_TIERS["free"]["pdf_uploads_per_month"],
        "text_queries_remaining": SUBSCRIPTION_TIERS["free"]["text_queries_per_month"],
        "text_queries_used": 0,
        "text_queries_limit": SUBSCRIPTION_TIERS["free"]["text_queries_per_month"],
        "subscription_expires": None
    }