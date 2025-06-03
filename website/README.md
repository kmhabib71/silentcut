# SilenceCutter SaaS Website

A modern, responsive SaaS website for the SilenceCutter application built with Next.js, TypeScript, and Tailwind CSS.

## Features

- 🎨 Modern, responsive design with dark theme
- 🔐 Authentication with NextAuth.js (Google OAuth + Email/Password)
- 💳 Subscription management with 2Checkout integration
- 📊 Admin dashboard for user management
- 🗄️ MongoDB Atlas integration
- 🚀 Optimized for Railway.app deployment
- 📱 Mobile-first responsive design
- ⚡ Fast loading with Next.js App Router

## Tech Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Authentication**: NextAuth.js
- **Database**: MongoDB Atlas with Mongoose
- **Payments**: 2Checkout (Verifone)
- **Animations**: Framer Motion
- **Icons**: Lucide React
- **Deployment**: Railway.app

## Getting Started

### Prerequisites

- Node.js 18+
- MongoDB Atlas account
- Google Cloud Console project (for OAuth)
- 2Checkout merchant account

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd website
```

2. Install dependencies:

```bash
npm install
```

3. Set up environment variables:

```bash
cp .env.example .env.local
```

4. Configure your `.env.local` file:

```env
# NextAuth Configuration
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-secret-key-here

# MongoDB Configuration
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/silence-cutter-saas

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# 2Checkout Payment Configuration
TWOCHECKOUT_MERCHANT_CODE=your-merchant-code
TWOCHECKOUT_SECRET_KEY=your-secret-key

# Admin Configuration
ADMIN_EMAIL=admin@yoursite.com

# Application URLs
PYTHON_APP_API_URL=http://localhost:5000
WEBSITE_URL=http://localhost:3000
```

5. Run the development server:

```bash
npm run dev
```

6. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
website/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── api/               # API routes
│   │   ├── auth/              # Authentication pages
│   │   ├── admin/             # Admin dashboard
│   │   ├── pricing/           # Pricing page
│   │   └── dashboard/         # User dashboard
│   ├── lib/                   # Utility libraries
│   │   ├── mongodb.ts         # Database connection
│   │   └── auth.ts            # NextAuth configuration
│   ├── models/                # Database models
│   │   └── User.ts            # User model
│   └── components/            # Reusable components
├── public/                    # Static assets
├── package.json
├── tailwind.config.js
├── next.config.js
└── tsconfig.json
```

## API Endpoints

### Public Endpoints

- `POST /api/validate-usage` - Validate file processing usage
- `POST /api/record-usage` - Record file processing usage
- `POST /api/auth/login` - Email/password authentication

### Protected Endpoints

- `GET /api/user/[id]` - Get user information
- `GET /api/subscription/status` - Check subscription status

### Admin Endpoints

- `GET /api/admin/users` - List all users
- `GET /api/admin/stats` - Get system statistics
- `POST /api/admin/users/ban` - Ban/unban users
- `POST /api/admin/users/subscription` - Update user subscriptions

## Database Schema

### User Model

```typescript
{
  email: string;
  name: string;
  password?: string;
  googleId?: string;
  avatar?: string;
  subscription: {
    plan: 'free' | 'monthly' | 'yearly';
    status: 'active' | 'cancelled' | 'expired';
    startDate: Date;
    endDate?: Date;
    paymentId?: string;
  };
  usage: {
    totalMinutesUsed: number;
    monthlyUsage: {
      month: string; // YYYY-MM format
      minutes: number;
    }[];
    lastResetDate: Date;
  };
  profile: {
    firstName?: string;
    lastName?: string;
    company?: string;
    timezone?: string;
  };
  banned: boolean;
  isAdmin: boolean;
  passwordResetToken?: string;
  passwordResetExpires?: Date;
  emailVerified: boolean;
  emailVerificationToken?: string;
  createdAt: Date;
  updatedAt: Date;
}
```

## Subscription Plans

### Free Plan

- 60 minutes per month
- Basic silence detection
- Standard processing speed
- Email support

### Monthly Plan ($9/month)

- Unlimited processing
- Advanced AI detection
- Priority processing
- Batch processing
- Premium support
- Custom presets

### Yearly Plan ($59/year)

- Everything in Monthly
- Save $49 per year (45% discount)
- Priority support
- Early access to features
- Custom integrations

## Deployment

### Railway.app Deployment

1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push to main branch

### Environment Variables for Production

```env
NEXTAUTH_URL=https://your-domain.railway.app
NEXTAUTH_SECRET=your-production-secret
MONGODB_URI=your-production-mongodb-uri
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
TWOCHECKOUT_MERCHANT_CODE=your-merchant-code
TWOCHECKOUT_SECRET_KEY=your-secret-key
```

## Python Application Integration

The website communicates with the Python application through the `features/api_communication.py` module:

```python
from features.api_communication import api_client

# Validate file usage before processing
result = api_client.validate_file_usage(file_duration_minutes=5.5)
if result['allowed']:
    # Process the file
    process_file()
    # Record usage
    api_client.record_usage(file_duration_minutes=5.5, file_name="example.mp4")
else:
    # Show upgrade message
    show_upgrade_dialog(result['message'])
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.

## Support

For support, email support@silencecutter.com or visit our help center.
