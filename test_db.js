const mongoose = require("mongoose");

// MongoDB connection
const MONGODB_URI =
  "mongodb+srv://habib:Khurshida71@cluster0.qqlnw.mongodb.net/silence_cutter?retryWrites=true&w=majority&appName=Cluster0";

// Simple schema for testing
const AnonymousSessionSchema = new mongoose.Schema(
  {
    sessionId: {
      type: String,
      required: true,
      unique: true,
      index: true,
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
    deviceInfo: {
      permanentId: String,
      machineId: String,
      deviceName: String,
      linkedEmail: String,
      lastSeen: Date,
      registeredOnline: {
        type: Boolean,
        default: false,
      },
      sessions: [String],
    },
  },
  {
    timestamps: true,
  }
);

const AnonymousSession = mongoose.model(
  "AnonymousSession",
  AnonymousSessionSchema
);

async function testDatabaseConnection() {
  try {
    console.log("🔗 Connecting to MongoDB...");
    await mongoose.connect(MONGODB_URI);
    console.log("✅ Connected to MongoDB successfully");

    // Test creating a session
    console.log("📝 Testing AnonymousSession creation...");

    const testSession = new AnonymousSession({
      sessionId: "test-session-12345",
      totalMinutesUsed: 2.5,
      filesProcessed: 1,
      firstUseDate: new Date(),
      lastUseDate: new Date(),
      ipAddress: "127.0.0.1",
      userAgent: "test-agent",
      files: [
        {
          fileName: "test-video.mp4",
          durationMinutes: 2.5,
          processedDate: new Date(),
        },
      ],
      deviceInfo: {
        permanentId: "test-device-id",
        deviceName: "Test Device",
        lastSeen: new Date(),
        registeredOnline: true,
      },
    });

    const savedSession = await testSession.save();
    console.log("✅ AnonymousSession created successfully:", savedSession._id);

    // Test finding the session
    const foundSession = await AnonymousSession.findOne({
      sessionId: "test-session-12345",
    });
    console.log("✅ Found session:", foundSession ? "Yes" : "No");

    // Clean up test data
    await AnonymousSession.deleteOne({ sessionId: "test-session-12345" });
    console.log("🧹 Test data cleaned up");

    console.log("\n🎉 Database test completed successfully!");
  } catch (error) {
    console.error("❌ Database test failed:", error.message);
    console.error("Full error:", error);
  } finally {
    await mongoose.disconnect();
    console.log("🔌 Disconnected from MongoDB");
  }
}

testDatabaseConnection();
