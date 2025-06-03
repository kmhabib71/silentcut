import mongoose, { Schema, Document } from "mongoose";

export interface IUser extends Document {
  email: string;
  name: string;
  password?: string;
  googleId?: string;
  avatar?: string;
  subscription: {
    plan: "free" | "monthly" | "yearly";
    status: "active" | "cancelled" | "expired";
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

const UserSchema: Schema = new Schema(
  {
    email: {
      type: String,
      required: true,
      unique: true,
      lowercase: true,
      trim: true,
    },
    name: {
      type: String,
      required: true,
      trim: true,
    },
    password: {
      type: String,
      select: false, // Don't include password in queries by default
    },
    googleId: {
      type: String,
      sparse: true, // Allow multiple null values
    },
    avatar: {
      type: String,
    },
    subscription: {
      plan: {
        type: String,
        enum: ["free", "monthly", "yearly"],
        default: "free",
      },
      status: {
        type: String,
        enum: ["active", "cancelled", "expired"],
        default: "active",
      },
      startDate: {
        type: Date,
        default: Date.now,
      },
      endDate: {
        type: Date,
      },
      paymentId: {
        type: String,
      },
    },
    usage: {
      totalMinutesUsed: {
        type: Number,
        default: 0,
      },
      monthlyUsage: [
        {
          month: String, // YYYY-MM format
          minutes: Number,
        },
      ],
      lastResetDate: {
        type: Date,
        default: Date.now,
      },
    },
    profile: {
      firstName: String,
      lastName: String,
      company: String,
      timezone: String,
    },
    banned: {
      type: Boolean,
      default: false,
    },
    isAdmin: {
      type: Boolean,
      default: false,
    },
    passwordResetToken: String,
    passwordResetExpires: Date,
    emailVerified: {
      type: Boolean,
      default: false,
    },
    emailVerificationToken: String,
  },
  {
    timestamps: true,
  }
);

// Indexes for better performance (removed duplicate email and googleId since they have unique: true)
UserSchema.index({ "subscription.plan": 1 });
UserSchema.index({ banned: 1 });
UserSchema.index({ isAdmin: 1 });

// Method to check if user can process file of given duration
UserSchema.methods.canProcessFile = function (durationMinutes: number) {
  const currentMonth = new Date().toISOString().slice(0, 7); // YYYY-MM
  const currentUsage = this.usage.monthlyUsage.find(
    (usage: { month: string; minutes: number }) => usage.month === currentMonth
  );
  const usedMinutes = currentUsage ? currentUsage.minutes : 0;

  if (this.subscription.plan === "free") {
    return usedMinutes + durationMinutes <= 60; // 60 minutes limit for free plan
  }

  return true; // Unlimited for paid plans
};

// Method to add usage
UserSchema.methods.addUsage = function (durationMinutes: number) {
  const currentMonth = new Date().toISOString().slice(0, 7); // YYYY-MM
  const currentUsageIndex = this.usage.monthlyUsage.findIndex(
    (usage: { month: string; minutes: number }) => usage.month === currentMonth
  );

  if (currentUsageIndex >= 0) {
    this.usage.monthlyUsage[currentUsageIndex].minutes += durationMinutes;
  } else {
    this.usage.monthlyUsage.push({
      month: currentMonth,
      minutes: durationMinutes,
    });
  }

  this.usage.totalMinutesUsed += durationMinutes;
  return this.save();
};

export default mongoose.models.User ||
  mongoose.model<IUser>("User", UserSchema);
