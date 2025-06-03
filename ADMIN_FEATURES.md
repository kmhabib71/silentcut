# Admin Features Documentation

## 🗄️ Database Control

### Manual Database Editing

**Local SQLite Database**: `C:\Users\WALTON\.silence_cutter\usage.db`

#### Option 1: Interactive Database Editor

```bash
python database_editor.py
```

Features:

- ✅ Show current usage data
- ✅ Set specific usage minutes (e.g., 58 minutes for testing free limit)
- ✅ Add test files with custom durations
- ✅ Quick presets (58 min, 65 min, reset to 0)

#### Option 2: Simple Clearing

```bash
python simple_clear.py          # Clear all data
python simple_clear.py --delete # Delete database file
```

#### Option 3: Manual File Access

- **SQLite Browser**: Download DB Browser for SQLite to manually edit
- **Direct File**: Delete `C:\Users\WALTON\.silence_cutter\usage.db` to reset completely

### Admin Panel Database Control

**Endpoint**: `/api/admin/database-control`

#### Remote Database Management

```javascript
// Set usage to specific minutes
POST /api/admin/database-control
{
  "action": "setUsage",
  "sessionId": "2b61c9e79c106d9a",
  "permanentId": "2b61c9e79c106d9a",
  "newUsage": 58
}

// Add additional minutes
POST /api/admin/database-control
{
  "action": "addTestUsage",
  "sessionId": "2b61c9e79c106d9a",
  "permanentId": "2b61c9e79c106d9a",
  "newUsage": 5
}

// Reset usage to 0
POST /api/admin/database-control
{
  "action": "resetUsage",
  "sessionId": "2b61c9e79c106d9a",
  "permanentId": "2b61c9e79c106d9a"
}
```

## 🚫 User Blocking System

### Block Users and Anonymous Sessions

**Endpoint**: `/api/admin/block-user`

#### Block a User/Session

```javascript
POST /api/admin/block-user
{
  "action": "block",
  "targetId": "user_id_or_session_id",
  "targetType": "user", // or "anonymous"
  "reason": "Violation of terms",
  "duration": 24, // hours (optional, permanent if not specified)
  "adminId": "admin_user_id"
}
```

#### Unblock a User/Session

```javascript
POST /api/admin/block-user
{
  "action": "unblock",
  "targetId": "user_id_or_session_id",
  "targetType": "user", // or "anonymous"
  "adminId": "admin_user_id"
}
```

#### Get All Blocked Users

```javascript
GET / api / admin / block - user;
// Returns list of all blocked users and anonymous sessions
```

### Blocking Features

- ✅ **Permanent blocking**: Block indefinitely
- ✅ **Temporary blocking**: Auto-expire after specified hours
- ✅ **Reason tracking**: Store reason for blocking
- ✅ **Admin tracking**: Track which admin performed the action
- ✅ **Dual support**: Block both registered users and anonymous sessions
- ✅ **Automatic enforcement**: Blocked users cannot process files

## 💳 Subscription Plans

### New Pricing Structure

**Endpoint**: `/api/admin/subscription-plans`

#### Available Plans

```javascript
{
  "free": {
    "name": "Free Plan",
    "price": 0,
    "monthlyMinutes": 60, // 1 hour per month
    "features": ["60 minutes per month", "Basic support"]
  },
  "monthly": {
    "name": "Monthly Plan",
    "price": 9, // $9/month
    "monthlyMinutes": -1, // Unlimited
    "features": ["Unlimited minutes per month", "Priority support", "Advanced features"]
  },
  "yearly": {
    "name": "Yearly Plan",
    "price": 59, // $59/year (20% savings)
    "monthlyMinutes": -1, // Unlimited
    "features": ["Unlimited minutes per year", "Priority support", "Advanced features", "20% savings"]
  }
}
```

#### Plan Management

```javascript
// Change user's plan
POST /api/admin/subscription-plans
{
  "action": "changePlan",
  "userId": "user_id",
  "newPlan": "monthly", // or "yearly", "free"
  "price": 9, // optional custom price
  "adminId": "admin_id"
}

// Cancel subscription
POST /api/admin/subscription-plans
{
  "action": "cancelSubscription",
  "userId": "user_id",
  "adminId": "admin_id"
}

// Extend subscription
POST /api/admin/subscription-plans
{
  "action": "extendSubscription",
  "userId": "user_id",
  "adminId": "admin_id"
}
```

#### Subscription Statistics

```javascript
GET / api / admin / subscription - plans;
// Returns:
// - Plan details and pricing
// - User distribution by plan
// - Revenue statistics
// - Usage analytics
```

## 🔒 Enhanced Security Features

### User Model Enhancements

- ✅ **Blocking system**: New `blocking` field with detailed tracking
- ✅ **Price tracking**: Store actual price paid for custom pricing
- ✅ **Plan validation**: Automatic usage limit enforcement
- ✅ **Backward compatibility**: Existing `banned` field still works

### Anonymous Session Blocking

- ✅ **Device-level blocking**: Block by permanent device ID
- ✅ **Session-level blocking**: Block specific sessions
- ✅ **IP-based tracking**: Enhanced monitoring capabilities

## 🧪 Testing Tools

### Comprehensive Test Suite

```bash
python test_admin_features.py
```

Tests:

- ✅ Database control (set usage to 58 minutes)
- ✅ User blocking/unblocking
- ✅ Subscription plan management
- ✅ Admin API functionality

### Usage Scenarios

1. **Test Free Limit**: Set usage to 58 minutes, try to process 5-minute file
2. **Test Blocking**: Block a session, verify it cannot process files
3. **Test Plans**: Upgrade user to monthly plan, verify increased limits

## 📊 Admin Dashboard Integration

### Database Control Panel

- View all sessions and usage data
- Set custom usage for testing
- Real-time usage monitoring

### User Management Panel

- Block/unblock users and sessions
- View blocking history and reasons
- Temporary vs permanent blocking options

### Subscription Management Panel

- Change user plans instantly
- View revenue and user statistics
- Cancel/extend subscriptions
- Custom pricing options

## 🚀 API Summary

| Feature            | Endpoint                        | Method   | Purpose                          |
| ------------------ | ------------------------------- | -------- | -------------------------------- |
| Database Control   | `/api/admin/database-control`   | POST/GET | Manually control usage data      |
| User Blocking      | `/api/admin/block-user`         | POST/GET | Block/unblock users and sessions |
| Subscription Plans | `/api/admin/subscription-plans` | POST/GET | Manage plans and pricing         |
| Anonymous Sessions | `/api/admin/anonymous-sessions` | GET      | View all anonymous usage         |

## ✅ Key Benefits

1. **Complete Control**: Full control over usage data for testing
2. **User Management**: Block problematic users instantly
3. **Flexible Pricing**: Three-tier pricing with custom options
4. **Testing Friendly**: Easy to set specific scenarios for testing
5. **Revenue Tracking**: Detailed subscription and revenue analytics
6. **Security**: Enhanced blocking system for both users and anonymous sessions

## 🎯 Perfect for Testing

- Set usage to 58 minutes to test free limit warnings
- Set usage to 65 minutes to test over-limit restrictions
- Block users to test access control
- Switch between plans to test different usage limits
- Monitor real-time usage and revenue data
