import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import AnonymousSession from "@/models/AnonymousSession";

export async function GET(request: NextRequest) {
  try {
    console.log("🔗 Testing database connection...");
    await connectToDatabase();
    console.log("✅ Database connected");

    console.log("📝 Testing AnonymousSession model...");
    const testSession = new AnonymousSession({
      sessionId: "test-endpoint-" + Date.now(),
      totalMinutesUsed: 1.0,
      filesProcessed: 1,
      firstUseDate: new Date(),
      lastUseDate: new Date(),
      files: [
        {
          fileName: "test.mp4",
          durationMinutes: 1.0,
          processedDate: new Date(),
        },
      ],
      deviceInfo: {
        permanentId: "test-device",
        deviceName: "Test Device",
        lastSeen: new Date(),
        registeredOnline: true,
      },
    });

    const saved = await testSession.save();
    console.log("✅ Test session saved:", saved._id);

    // Clean up
    await AnonymousSession.deleteOne({ _id: saved._id });
    console.log("🧹 Test data cleaned up");

    return NextResponse.json({
      success: true,
      message: "Database and model test passed",
      testId: saved._id,
    });
  } catch (error: any) {
    console.error("❌ Test failed:", error);
    return NextResponse.json(
      {
        error: "Test failed",
        message: error.message,
        stack: error.stack,
      },
      { status: 500 }
    );
  }
}
