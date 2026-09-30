"""Saberlink Payments Module

This module handles payment processing and subscription management.
It follows the modular architecture principle: this module can be deleted
without breaking the core saberlink functionality.

Dependencies:
- backend/api/usage_limits.py: Usage tracking and limits enforcement
- RevenueCat SDK: For payment processing (optional, sandbox mode available)

Usage:
    from saberlink.payments import validate_subscription, process_payment
    
    # Validate user subscription status
    status = validate_subscription(user_id)
    
    # Process payment (with RevenueCat or fallback)
    result = process_payment(user_id, payment_data)
"""

from __future__ import annotations

from saberlink.payments.subscription import (
    validate_subscription,
    process_subscription_update,
    get_subscription_tiers,
    check_usage_limits
)
from saberlink.payments.catalog import (
    get_product,
    get_offering,
    get_package_limits,
    get_entitlements_from_package,
    map_revenuecat_to_catalog,
    get_usage_limits_from_entitlements
)
from saberlink.payments.purchase_flow import (
    get_offerings_for_user,
    validate_purchase_eligibility,
    simulate_purchase,
    restore_purchases,
    check_entitlement_status,
    handle_purchase_error,
    get_customer_info
)
from saberlink.payments.webhooks import (
    verify_webhook_signature,
    process_webhook_event,
    sync_customer_info,
    validate_access_from_server,
    get_webhook_history,
    log_webhook_event
)

__all__ = [
    # Subscription
    "validate_subscription",
    "process_subscription_update", 
    "get_subscription_tiers",
    "check_usage_limits",
    
    # Catalog
    "get_product",
    "get_offering",
    "get_package_limits",
    "get_entitlements_from_package",
    "map_revenuecat_to_catalog",
    "get_usage_limits_from_entitlements",
    
    # Purchase Flow
    "get_offerings_for_user",
    "validate_purchase_eligibility",
    "simulate_purchase",
    "restore_purchases",
    "check_entitlement_status",
    "handle_purchase_error",
    "get_customer_info",
    
    # Webhooks
    "verify_webhook_signature",
    "process_webhook_event",
    "sync_customer_info",
    "validate_access_from_server",
    "get_webhook_history",
    "log_webhook_event"
]