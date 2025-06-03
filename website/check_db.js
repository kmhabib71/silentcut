const mongoose = require("mongoose");

// MongoDB connection
const MONGODB_URI =
  "mongodb+srv://habib:Khurshida71@cluster0.qqlnw.mongodb.net/silence_cutter?retryWrites=true&w=majority&appName=Cluster0";

// Simple schema for checking
const AnonymousSessionSchema = new mongoose.Schema(
  {
    sessionId: String,
    totalMinutesUsed: Number,
    filesProcessed: Number,
    firstUseDate: Date,
    lastUseDate: Date,
    files: [
      {
        fileName: String,
        durationMinutes: Number,
        processedDate: Date,
      },
    ],
    deviceInfo: {
      permanentId: String,
      deviceName: String,
      lastSeen: Date,
      registeredOnline: Boolean,
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

async function checkDatabase() {
  try {
    console.log("🔗 Connecting to MongoDB...");
    await mongoose.connect(MONGODB_URI);
    console.log("✅ Connected to MongoDB successfully");

    console.log("📊 Checking anonymous sessions...");
    const sessions = await AnonymousSession.find({})
      .sort({ lastUseDate: -1 })
      .limit(5);

    console.log(`\n📱 Found ${sessions.length} anonymous sessions:`);

    sessions.forEach((session, index) => {
      console.log(`\n${index + 1}. Session ID: ${session.sessionId}`);
      console.log(`   Minutes Used: ${session.totalMinutesUsed}`);
      console.log(`   Files Processed: ${session.filesProcessed}`);
      console.log(`   Device: ${session.deviceInfo?.deviceName || "Unknown"}`);
      console.log(`   Last Used: ${session.lastUseDate}`);
      console.log(`   Files: ${session.files?.length || 0} files`);

      if (session.files && session.files.length > 0) {
        console.log(`   Recent files:`);
        session.files.slice(-3).forEach((file, i) => {
          console.log(`     - ${file.fileName} (${file.durationMinutes} min)`);
        });
      }
    });

    // Check for our specific test device
    console.log("\n🔍 Looking for test device (2b61c9e79c106d9a)...");
    const testDevice = await AnonymousSession.findOne({
      sessionId: "2b61c9e79c106d9a",
    });

    if (testDevice) {
      console.log("✅ Test device found in database!");
      console.log(`   Total usage: ${testDevice.totalMinutesUsed} minutes`);
      console.log(`   Files processed: ${testDevice.filesProcessed}`);
      console.log(`   Device name: ${testDevice.deviceInfo?.deviceName}`);
      console.log(`   Files in database: ${testDevice.files?.length || 0}`);
    } else {
      console.log("❌ Test device not found in database");
    }

    console.log("\n🎉 Database check completed!");
  } catch (error) {
    console.error("❌ Database check failed:", error.message);
  } finally {
    await mongoose.disconnect();
    console.log("🔌 Disconnected from MongoDB");
  }
}

checkDatabase();
