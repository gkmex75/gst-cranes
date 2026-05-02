# linkedin-ads.py
# SP4 LinkedIn Marketing API targeted campaign create.
# Matched Audience + Industry filter has known interaction (function breakdown
# required; see memory feedback_linkedin_matched_audience.md). v1: skeleton.
import os
import requests


LINKEDIN_API_VERSION = "202504"
ADS_API_BASE = "https://api.linkedin.com/rest"


def create_targeted_campaign(args: dict) -> dict:
    """
    args: {
      promotion_id, headline, intro_text, destination_url,
      ad_account_id, audience_id, budget_eur, duration_days
    }
    Returns: { campaign_id, ad_urn }
    """
    token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
        "Content-Type": "application/json",
    }
    budget = min(args["budget_eur"], int(os.environ["LINKEDIN_AD_BUDGET_EUR"]))

    # 1. Campaign create
    campaign_payload = {
        "name": f"GST Promote {args['promotion_id']}",
        "type": "SPONSORED_UPDATES",
        "status": "ACTIVE",
        "account": f"urn:li:sponsoredAccount:{args['ad_account_id']}",
        "campaignGroup": f"urn:li:sponsoredCampaignGroup:{os.environ['LINKEDIN_CAMPAIGN_GROUP_ID']}",
        "dailyBudget": {
            "amount": str(budget // args["duration_days"] * 100),
            "currencyCode": "EUR",
        },
        "totalBudget": {"amount": str(budget * 100), "currencyCode": "EUR"},
        "objectiveType": "WEBSITE_VISIT",
        "targetingCriteria": {
            "include": {
                "and": [
                    {
                        "or": {
                            "urn:li:adTargetingFacet:audienceMatchingSegments": [
                                f"urn:li:audienceMatchingSegment:{args['audience_id']}"
                            ]
                        }
                    }
                ]
            }
        },
    }
    r = requests.post(
        f"{ADS_API_BASE}/adCampaigns",
        headers=headers,
        json=campaign_payload,
        timeout=30,
    )
    r.raise_for_status()
    campaign_id = r.headers.get("x-restli-id") or r.json().get("id")

    # 2. Ad creative + ad create — TODO Phase F4 smoke (Task 18) detailed sequence.
    # Plan 4 v1 spec section 5.4 has the full chain.
    return {"campaign_id": campaign_id, "ad_urn": "TODO"}
