import mongoose, { Schema, Document, Model } from "mongoose";

export interface IAnonymousSession extends Document {
  sessionId: string;
  totalMinutesUsed: number;
  filesProcessed: number;
  firstUseDate: Date;
  lastUseDate: Date;
  ipAddress?: string;
  userAgent?: string;
  location?: {
    country?: string;
    region?: string;
    city?: string;
  };
  files: {
    fileName: string;
    durationMinutes: number;
    processedDate: Date;
  }[];
  syncedToUser?: string; // User ID if later associated
  deviceInfo?: {
    permanentId: string;
    machineId?: string;
    deviceName?: string;
    linkedEmail?: string;
    lastSeen: Date;
    registeredOnline?: boolean;
    sessions?: string[];
  };
  blocking?: {
    isBlocked: boolean;
    blockedAt?: Date;
    blockedBy?: string; // Admin who blocked
    reason?: string;
    blockedUntil?: Date; // Optional expiry date for temporary blocks
  };
  createdAt: Date;
  updatedAt: Date;
}

interface IAnonymousSessionModel extends Model<IAnonymousSession> {
  getSessionStats(): Promise<any[]>;
  getRecentActivity(days?: number): Promise<any[]>;
}

const AnonymousSessionSchema: Schema = new Schema(
  {
    sessionId: {
      type: String,
      required: true,
      unique: true,
    },
    totalMinutesUsed: {
      type: Number,
      default: 0,
      min: 0,
    },
    filesProcessed: {
      type: Number,
      default: 0,
      min: 0,
    },
    firstUseDate: {
      type: Date,
      required: true,
    },
    lastUseDate: {
      type: Date,
      required: true,
    },
    ipAddress: {
      type: String,
      sparse: true,
    },
    userAgent: {
      type: String,
    },
    location: {
      country: String,
      region: String,
      city: String,
    },
    files: [
      {
        fileName: {
          type: String,
          required: true,
        },
        durationMinutes: {
          type: Number,
          required: true,
          min: 0,
        },
        processedDate: {
          type: Date,
          required: true,
        },
      },
    ],
    syncedToUser: {
      type: Schema.Types.ObjectId,
      ref: "User",
      sparse: true,
    },
    deviceInfo: {
      permanentId: {
        type: String,
        required: false,
      },
      machineId: {
        type: String,
        required: false,
      },
      deviceName: {
        type: String,
        required: false,
      },
      linkedEmail: {
        type: String,
        required: false,
      },
      lastSeen: {
        type: Date,
        required: false,
      },
      registeredOnline: {
        type: Boolean,
        default: false,
      },
      sessions: [
        {
          type: String,
        },
      ],
    },
    blocking: {
      isBlocked: {
        type: Boolean,
        default: false,
      },
      blockedAt: {
        type: Date,
      },
      blockedBy: {
        type: String,
      },
      reason: {
        type: String,
      },
      blockedUntil: {
        type: Date,
      },
    },
  },
  {
    timestamps: true,
  }
);

// Indexes for better performance
AnonymousSessionSchema.index({ sessionId: 1 });
AnonymousSessionSchema.index({ lastUseDate: -1 });
AnonymousSessionSchema.index({ totalMinutesUsed: -1 });
AnonymousSessionSchema.index({ createdAt: -1 });

// Static methods for analytics
AnonymousSessionSchema.statics.getSessionStats = function () {
  return this.aggregate([
    {
      $group: {
        _id: null,
        totalSessions: { $sum: 1 },
        totalMinutesProcessed: { $sum: "$totalMinutesUsed" },
        totalFilesProcessed: { $sum: "$filesProcessed" },
        avgMinutesPerSession: { $avg: "$totalMinutesUsed" },
        avgFilesPerSession: { $avg: "$filesProcessed" },
      },
    },
  ]);
};

AnonymousSessionSchema.statics.getRecentActivity = function (days = 30) {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  return this.aggregate([
    {
      $match: {
        lastUseDate: { $gte: startDate },
      },
    },
    {
      $group: {
        _id: {
          $dateToString: {
            format: "%Y-%m-%d",
            date: "$lastUseDate",
          },
        },
        sessions: { $sum: 1 },
        minutesProcessed: { $sum: "$totalMinutesUsed" },
        filesProcessed: { $sum: "$filesProcessed" },
      },
    },
    {
      $sort: { _id: 1 },
    },
  ]);
};

export default (mongoose.models.AnonymousSession ||
  mongoose.model<IAnonymousSession, IAnonymousSessionModel>(
    "AnonymousSession",
    AnonymousSessionSchema
  )) as IAnonymousSessionModel;
