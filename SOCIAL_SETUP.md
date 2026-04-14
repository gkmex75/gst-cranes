# Social Media API Setup Guide

## 1. Meta (Facebook + Instagram)

### Prerequisites
- A Facebook Page for GST Cranes
- An Instagram Business Account linked to that Facebook Page
- A Meta Developer account

### Step-by-Step

#### A. Create a Meta App
1. Go to https://developers.facebook.com/apps/
2. Click **"Create App"**
3. Choose **"Business"** type
4. App name: `GST Cranes Automation`
5. Select your Business Portfolio (or create one)

#### B. Add Products
1. In your app dashboard, click **"Add Product"**
2. Add **"Facebook Login for Business"**
3. Add **"Instagram Graph API"**

#### C. Get a Page Access Token
1. Go to https://developers.facebook.com/tools/explorer/
2. Select your app from the dropdown
3. Click **"Generate Access Token"**
4. Grant these permissions:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
5. Copy the **User Access Token**
6. Exchange it for a **long-lived token** (60 days):
   ```
   GET https://graph.facebook.com/v21.0/oauth/access_token?
     grant_type=fb_exchange_token&
     client_id=YOUR_APP_ID&
     client_secret=YOUR_APP_SECRET&
     fb_exchange_token=SHORT_LIVED_TOKEN
   ```
7. Then get a **Page Access Token** (never expires):
   ```
   GET https://graph.facebook.com/v21.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN
   ```
   Find your GST Cranes page in the response and copy its `access_token`.

#### D. Get Page ID and Instagram Account ID
1. **Page ID**: Found in the response above, or go to your Page -> About -> Page ID
2. **Instagram Account ID**:
   ```
   GET https://graph.facebook.com/v21.0/PAGE_ID?fields=instagram_business_account&access_token=PAGE_TOKEN
   ```
   Copy the `instagram_business_account.id` value.

#### E. Add to .env
```
META_PAGE_ACCESS_TOKEN=your_page_access_token
META_PAGE_ID=your_page_id
META_INSTAGRAM_ACCOUNT_ID=your_instagram_business_account_id
```

### Testing
```bash
# Verify token works
curl "https://graph.facebook.com/v21.0/me?access_token=YOUR_TOKEN"
```

---

## 2. LinkedIn

### Prerequisites
- Admin access to the GST Cranes LinkedIn Company Page
- A LinkedIn Developer account

### Step-by-Step

#### A. Create a LinkedIn App
1. Go to https://www.linkedin.com/developers/apps
2. Click **"Create app"**
3. App name: `GST Cranes Automation`
4. LinkedIn Page: Select GST Cranes company page
5. Upload a logo (use GST Cranes logo)
6. Accept terms

#### B. Request API Products
1. In your app, go to the **"Products"** tab
2. Request access to:
   - **Share on LinkedIn** (for posting)
   - **Sign In with LinkedIn using OpenID Connect**
3. Wait for approval (usually instant for Share on LinkedIn)

#### C. Configure OAuth
1. Go to **"Auth"** tab
2. Add redirect URL: `https://localhost:8443/callback`
3. Note your **Client ID** and **Client Secret**
4. Required scopes: `w_member_social`, `w_organization_social`, `r_organization_social`

#### D. Get an Access Token
1. Open this URL in a browser (replace CLIENT_ID):
   ```
   https://www.linkedin.com/oauth/v2/authorization?
     response_type=code&
     client_id=YOUR_CLIENT_ID&
     redirect_uri=https://localhost:8443/callback&
     scope=w_member_social%20w_organization_social%20r_organization_social
   ```
2. Authorize the app
3. You'll be redirected to `https://localhost:8443/callback?code=AUTH_CODE`
4. Copy the `code` parameter
5. Exchange for access token:
   ```bash
   curl -X POST https://www.linkedin.com/oauth/v2/accessToken \
     -d "grant_type=authorization_code" \
     -d "code=AUTH_CODE" \
     -d "redirect_uri=https://localhost:8443/callback" \
     -d "client_id=YOUR_CLIENT_ID" \
     -d "client_secret=YOUR_CLIENT_SECRET"
   ```
6. Copy the `access_token` (valid for 60 days)

#### E. Get Organization ID
Your LinkedIn Company Page URL looks like: `linkedin.com/company/gst-cranes/`
The Organization ID can be found via:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://api.linkedin.com/v2/organizationAcls?q=roleAssignee"
```
Look for your organization's ID in the response.

#### F. Add to .env
```
LINKEDIN_ACCESS_TOKEN=your_access_token
LINKEDIN_ORGANIZATION_ID=your_org_id
```

---

## Token Refresh Reminders

| Platform | Token Lifetime | How to Refresh |
|----------|---------------|----------------|
| Meta Page Token | Never expires | No action needed (if obtained correctly) |
| LinkedIn | 60 days | Re-run OAuth flow above |

The script will warn you when tokens are about to expire or have expired.
