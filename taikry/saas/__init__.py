"""
ZYROX AI SaaS Platform Package
Exposes core authentication, trial enforcement, entitlement gating, and administrative services.
"""

from taikry.saas.security import (
    hash_password,
    verify_password,
    generate_session_token,
    hash_token,
    auth_rate_limiter
)
from taikry.saas.auth_service import (
    sign_up_user,
    login_user,
    authenticate_session,
    logout_user,
    verify_email_token,
    request_password_reset,
    reset_password,
    delete_user_account
)
from taikry.saas.trial_service import (
    grant_14_day_trial,
    get_user_trial_status
)
from taikry.saas.entitlement_service import (
    get_all_plans,
    get_user_entitlement,
    check_and_consume_quota,
    init_default_plans
)
from taikry.saas.telegram_link_service import (
    generate_telegram_linking_token,
    process_telegram_webhook_linking,
    unlink_telegram_account,
    get_telegram_link_status,
    update_notification_preferences
)
from taikry.saas.support_service import (
    create_support_ticket,
    get_user_tickets,
    admin_list_all_tickets,
    admin_reply_ticket
)
from taikry.saas.admin_service import (
    is_admin_user,
    bootstrap_admin_if_needed,
    admin_list_users,
    admin_set_user_status,
    admin_override_user_subscription,
    admin_get_analytics_summary,
    admin_get_audit_logs
)
from taikry.saas.billing_adapter import billing_adapter

