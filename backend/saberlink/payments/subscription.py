"""Subscription management module for Saberlink payments.

This module provides a clean interface for subscription management,
abstracting the RevenueCat integration and usage tracking.

It follows the modular architecture: can be deleted without breaking core functionality.
"""

from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime


def validate_subscription(user_id: str) -> Dict:
    """Validate user's current subscription status.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        Dict with subscription status, tier, and usage information
    """
    from saberlink import config
    from pathlib import Path
    import json
    
    # Load usage data from the centralized tracking system
    usage_file = config.PROCESSED_DIR / "usage_tracking.json"
    
    try:
        if usage_file.exists():
            data = json.loads(usage_file.read_text())
            user_data = data.get(user_id, {})
            
            return {
                "user_id": user_id,
                "current_tier": user_data.get("current_tier", "free"),
                "subscription_expires": user_data.get("subscription_expires"),
                "pdf_uploads_used": user_data.get("pdf_uploads_this_month", 0),
                "text_queries_used": user_data.get("text_queries_this_month", 0),
                "last_reset": user_data.get("last_reset"),
                "is_active": True
            }
    except Exception:
        pass
    
    # Return default free tier if no data found
    return {
        "user_id": user_id,
        "current_tier": "free",
        "subscription_expires": None,
        "pdf_uploads_used": 0,
        "text_queries_used": 0,
        "last_reset": datetime.now().isoformat(),
        "is_active": True
    }


def process_subscription_update(user_id: str, revenuecat_data: Dict) -> Dict:
    """Process subscription update from RevenueCat.
    
    Args:
        user_id: Unique identifier for the user
        revenuecat_data: Subscription data from RevenueCat SDK
        
    Returns:
        Dict with updated subscription status and usage limits
    """
    from saberlink import config
    from pathlib import Path
    import json
    
    usage_file = config.PROCESSED_DIR / "usage_tracking.json"
    
    # Ensure usage file exists
    if not usage_file.exists():
        usage_file.parent.mkdir(parents=True, exist_ok=True)
        usage_file.write_text("{}")
    
    # Load current data
    data = json.loads(usage_file.read_text())
    
    # Determine tier from RevenueCat data
    entitlements = revenuecat_data.get("entitlements", {})
    
    if "pro" in entitlements and entitlements["pro"].get("isActive", False):
        expiration = entitlements["pro"].get("expiresDate")
        product_id = entitlements["pro"].get("productIdentifier", "")
        
        # Determine if monthly or yearly
        if "yearly" in product_id.lower() or "annual" in product_id.lower():
            tier = "pro_yearly"
        else:
            tier = "pro_monthly"
    else:
        tier = "free"
        expiration = None
    
    # Update user data
    if user_id not in data:
        data[user_id] = {}
    
    data[user_id]["current_tier"] = tier
    data[user_id]["subscription_expires"] = expiration
    data[user_id]["last_updated"] = datetime.now().isoformat()
    
    # Save updated data
    usage_file.write_text(json.dumps(data, indent=2))
    
    # Return updated usage info
    return validate_subscription(user_id)


def get_subscription_tiers() -> Dict:
    """Get available subscription tiers and their limits.
    
    Returns:
        Dict with tier information and limits
    """
    return {
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


def check_usage_limits(user_id: str, action_type: str) -> Dict:
    """Check if user has available usage for a specific action.
    
    Args:
        user_id: Unique identifier for the user
        action_type: "pdf_upload" or "text_query"
        
    Returns:
        Dict with allowed status and remaining usage
    """
    subscription = validate_subscription(user_id)
    tiers = get_subscription_tiers()
    
    current_tier = subscription["current_tier"]
    tier_limits = tiers.get(current_tier, tiers["free"])
    
    if action_type == "pdf_upload":
        used = subscription["pdf_uploads_used"]
        limit = tier_limits["pdf_uploads_per_month"]
        remaining = max(0, limit - used)
        
        return {
            "allowed": used < limit,
            "action": "pdf_upload",
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "tier": current_tier
        }
    
    elif action_type == "text_query":
        used = subscription["text_queries_used"]
        limit = tier_limits["text_queries_per_month"]
        remaining = max(0, limit - used)
        
        return {
            "allowed": used < limit,
            "action": "text_query",
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "tier": current_tier
        }
    
    return {
        "allowed": False,
        "error": "Invalid action type"
    }


def track_usage(user_id: str, action_type: str) -> bool:
    """Track usage for a specific action.
    
    Args:
        user_id: Unique identifier for the user
        action_type: "pdf_upload" or "text_query"
        
    Returns:
        True if usage was tracked successfully, False if limit reached
    """
    from saberlink import config
    from pathlib import Path
    import json
    
    # First check if action is allowed
    check = check_usage_limits(user_id, action_type)
    if not check["allowed"]:
        return False
    
    # Load and update usage data
    usage_file = config.PROCESSED_DIR / "usage_tracking.json"
    
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
    
    # Increment appropriate counter
    if action_type == "pdf_upload":
        data[user_id]["pdf_uploads_this_month"] = data[user_id].get("pdf_uploads_this_month", 0) + 1
    elif action_type == "text_query":
        data[user_id]["text_queries_this_month"] = data[user_id].get("text_queries_this_month", 0) + 1
    
    # Save updated data
    usage_file.write_text(json.dumps(data, indent=2))
    
    return True